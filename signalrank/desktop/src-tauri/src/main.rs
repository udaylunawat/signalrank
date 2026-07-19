use std::env;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Emitter, Manager};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use url::Url;
use uuid::Uuid;

struct DesktopChildren {
    backend: Mutex<Option<CommandChild>>,
    web: Mutex<Option<CommandChild>>,
    shutting_down: Arc<AtomicBool>,
}

struct StartupDiagnostics {
    log_path: PathBuf,
}

enum ServiceWait {
    Ready,
    Exited,
    TimedOut,
}

impl DesktopChildren {
    fn stop(&self) {
        if self.shutting_down.swap(true, Ordering::SeqCst) {
            return;
        }

        let backend = self.backend.lock().ok().and_then(|mut child| child.take());
        let web = self.web.lock().ok().and_then(|mut child| child.take());
        let children = [web, backend];

        for child in children.iter().flatten() {
            terminate_process_tree(child.pid(), false);
        }
        thread::sleep(Duration::from_millis(1500));
        for child in children.iter().flatten() {
            terminate_process_tree(child.pid(), true);
        }
        for child in children.into_iter().flatten() {
            let _ = child.kill();
        }
    }
}

impl Drop for DesktopChildren {
    fn drop(&mut self) {
        self.stop();
    }
}

#[cfg(unix)]
fn unix_descendants(root_pid: u32) -> Vec<u32> {
    let output = match Command::new("ps").args(["-axo", "pid=,ppid="]).output() {
        Ok(output) if output.status.success() => output,
        _ => return Vec::new(),
    };
    let rows: Vec<(u32, u32)> = String::from_utf8_lossy(&output.stdout)
        .lines()
        .filter_map(|line| {
            let mut fields = line.split_whitespace();
            Some((fields.next()?.parse().ok()?, fields.next()?.parse().ok()?))
        })
        .collect();
    let mut result = Vec::new();
    let mut pending = vec![root_pid];
    while let Some(parent) = pending.pop() {
        for (pid, ppid) in &rows {
            if *ppid == parent {
                pending.push(*pid);
                result.push(*pid);
            }
        }
    }
    result.reverse();
    result
}

#[cfg(unix)]
fn terminate_process_tree(pid: u32, force: bool) {
    let signal = if force { "-KILL" } else { "-TERM" };
    for child_pid in unix_descendants(pid).into_iter().chain([pid]) {
        let _ = Command::new("kill")
            .args([signal, &child_pid.to_string()])
            .status();
    }
}

#[cfg(windows)]
fn terminate_process_tree(pid: u32, force: bool) {
    let mut args = vec!["/PID".to_string(), pid.to_string(), "/T".to_string()];
    if force {
        args.push("/F".to_string());
    }
    let _ = Command::new("taskkill").args(args).status();
}

fn stop_sidecars(app: &tauri::AppHandle) {
    if let Some(children) = app.try_state::<DesktopChildren>() {
        children.stop();
    }
}

fn allocate_ports() -> std::io::Result<(u16, u16)> {
    let backend = std::net::TcpListener::bind(("127.0.0.1", 0))?;
    let web = std::net::TcpListener::bind(("127.0.0.1", 0))?;
    Ok((backend.local_addr()?.port(), web.local_addr()?.port()))
}

fn wait_for_port(port: u16, timeout: Duration, exited: &AtomicBool) -> ServiceWait {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if exited.load(Ordering::SeqCst) {
            return ServiceWait::Exited;
        }
        if std::net::TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return ServiceWait::Ready;
        }
        thread::sleep(Duration::from_millis(150));
    }
    ServiceWait::TimedOut
}

fn random_secret() -> String {
    format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple())
}

fn load_install_secret(data_dir: &Path) -> std::io::Result<String> {
    let secret = std::fs::read_to_string(data_dir.join("install-secret"))?;
    let secret = secret.trim().to_string();
    if secret.len() < 32 {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "desktop install secret is invalid",
        ));
    }
    Ok(secret)
}

fn is_desktop_session_cookie(name: &str) -> bool {
    name.starts_with("signalrank.desktop.")
}

fn clear_desktop_session_cookies(window: &tauri::WebviewWindow) -> tauri::Result<()> {
    for cookie in window.cookies()? {
        if is_desktop_session_cookie(cookie.name()) {
            window.delete_cookie(cookie)?;
        }
    }
    Ok(())
}

fn find_server_js(directory: &Path) -> std::io::Result<Option<PathBuf>> {
    let direct = directory.join("server.js");
    if direct.is_file() {
        return Ok(Some(direct));
    }
    for entry in std::fs::read_dir(directory)? {
        let path = entry?.path();
        if path.is_dir() {
            if let Some(server) = find_server_js(&path)? {
                return Ok(Some(server));
            }
        }
    }
    Ok(None)
}

fn append_startup_log(path: &Path, message: &str) {
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{message}");
    }
}

fn splash_status(window: &tauri::WebviewWindow, message: &str, failed: bool) {
    let script = format!(
        "const status=document.querySelector('.status');\
         if(status){{status.textContent={message:?};status.classList.toggle('failed',{failed});}}\
         document.querySelector('.spinner')?.classList.toggle('hidden',{failed});\
         document.querySelector('.actions')?.classList.toggle('visible',{failed});"
    );
    let _ = window.eval(&script);
    if failed {
        let retry_window = window.clone();
        tauri::async_runtime::spawn(async move {
            for delay in [250, 750, 1500] {
                thread::sleep(Duration::from_millis(delay));
                let _ = retry_window.eval(&script);
            }
        });
    }
}

fn startup_status(handle: &tauri::AppHandle, log_path: &Path, message: &str) {
    append_startup_log(log_path, message);
    if let Some(window) = handle.get_webview_window("main") {
        splash_status(&window, message, false);
    }
}

fn startup_error(handle: &tauri::AppHandle, log_path: &Path, message: &str) {
    append_startup_log(log_path, &format!("Startup failed: {message}"));
    if let Some(window) = handle.get_webview_window("main") {
        splash_status(
            &window,
            "SignalRank could not start its local services. Retry, or open the startup log for details.",
            true,
        );
    }
}

fn sanitized_filename(filename: &str) -> String {
    let basename = Path::new(filename)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("signalrank-export.csv");
    let mut result: String = basename
        .chars()
        .take(128)
        .map(|character| {
            if character.is_ascii_alphanumeric() || matches!(character, '.' | '-' | '_' | ' ') {
                character
            } else {
                '_'
            }
        })
        .collect();
    while result.starts_with('.') {
        result.remove(0);
    }
    if result.trim().is_empty() {
        "signalrank-export.csv".to_string()
    } else {
        result
    }
}

#[tauri::command]
fn open_external(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let parsed = validated_external_url(&url)?;
    app.opener()
        .open_url(parsed.as_str(), None::<&str>)
        .map_err(|error| error.to_string())
}

fn validated_external_url(url: &str) -> Result<Url, String> {
    let parsed = Url::parse(url).map_err(|_| "The link is not a valid URL".to_string())?;
    if parsed.scheme() != "https" || parsed.host_str().is_none() {
        return Err("Only absolute HTTPS links can be opened".to_string());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("Links containing credentials are not allowed".to_string());
    }
    Ok(parsed)
}

#[tauri::command]
fn save_download(app: tauri::AppHandle, filename: String, data: Vec<u8>) -> Result<bool, String> {
    if data.len() > 25 * 1024 * 1024 {
        return Err("Exports larger than 25 MiB are not supported".to_string());
    }
    let destination = app
        .dialog()
        .file()
        .set_file_name(sanitized_filename(&filename))
        .blocking_save_file();
    let Some(destination) = destination else {
        return Ok(false);
    };
    let path = destination
        .into_path()
        .map_err(|error| format!("Invalid save destination: {error}"))?;
    std::fs::write(path, data).map_err(|error| format!("Unable to save export: {error}"))?;
    Ok(true)
}

#[tauri::command]
fn restart_app(app: tauri::AppHandle) {
    app.restart();
}

#[tauri::command]
fn reveal_startup_log(
    app: tauri::AppHandle,
    diagnostics: tauri::State<StartupDiagnostics>,
) -> Result<(), String> {
    app.opener()
        .reveal_item_in_dir(&diagnostics.log_path)
        .map_err(|error| error.to_string())
}

fn setup_packaged_sidecars(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    if cfg!(debug_assertions) {
        return Ok(());
    }

    let handle = app.handle().clone();
    let data_dir = env::var("SIGNALRANK_APP_DATA_DIR")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .map(PathBuf::from)
        .unwrap_or(handle.path().app_data_dir()?);
    std::fs::create_dir_all(&data_dir)?;
    let startup_log = data_dir.join("startup.log");
    std::fs::write(&startup_log, "SignalRank desktop startup\n")?;
    app.manage(StartupDiagnostics {
        log_path: startup_log.clone(),
    });

    let (backend_port, web_port) = allocate_ports()?;
    let bootstrap_token = random_secret();
    let shutting_down = Arc::new(AtomicBool::new(false));
    app.manage(DesktopChildren {
        backend: Mutex::new(None),
        web: Mutex::new(None),
        shutting_down: shutting_down.clone(),
    });

    tauri::async_runtime::spawn(async move {
        let result = start_sidecars(
            handle.clone(),
            data_dir,
            backend_port,
            web_port,
            bootstrap_token,
            shutting_down,
            startup_log.clone(),
        )
        .await;
        if let Err(error) = result {
            eprintln!("[desktop] startup failed: {error}");
            startup_error(&handle, &startup_log, &error.to_string());
            let _ = handle.emit("signalrank-sidecar-exit", "startup");
            stop_sidecars(&handle);
        }
    });
    Ok(())
}

async fn start_sidecars(
    handle: tauri::AppHandle,
    data_dir: PathBuf,
    backend_port: u16,
    web_port: u16,
    bootstrap_token: String,
    shutting_down: Arc<AtomicBool>,
    startup_log: PathBuf,
) -> Result<(), Box<dyn std::error::Error>> {
    let desktop_parent_pid = std::process::id().to_string();
    let backend_url = format!("http://127.0.0.1:{backend_port}");
    let web_url = format!("http://127.0.0.1:{web_port}");
    let resource_dir = handle.path().resource_dir()?;
    let server_js = find_server_js(&resource_dir.join("web"))?
        .ok_or("Bundled Next.js server.js was not found")?;
    let web_server = format!(
        "./{}",
        server_js
            .strip_prefix(&resource_dir)?
            .to_string_lossy()
            .replace('\\', "/")
    );
    let embedding_model = resource_dir.join("models").join("all-MiniLM-L6-v2");

    startup_status(
        &handle,
        &startup_log,
        "Starting the local database and ranking service…",
    );
    let backend_exited = Arc::new(AtomicBool::new(false));

    let mut backend_command = handle.shell().sidecar("signalrank-backend")?;
    #[cfg(target_os = "macos")]
    {
        backend_command =
            backend_command.env("PYTHON_KEYRING_BACKEND", "keyring.backends.macOS.Keyring");
    }
    let (mut backend_events, backend_child) = backend_command
        .env("HOST", "127.0.0.1")
        .env("PORT", backend_port.to_string())
        .env("SIGNALRANK_MODE", "desktop")
        .env("SIGNALRANK_DESKTOP_PARENT_PID", &desktop_parent_pid)
        .env("SIGNALRANK_APP_DATA_DIR", &data_dir)
        .env("SIGNALRANK_EMBEDDING_MODEL_PATH", embedding_model)
        .env(
            "SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN",
            bootstrap_token.clone(),
        )
        .spawn()?;
    if let Some(children) = handle.try_state::<DesktopChildren>() {
        if let Ok(mut slot) = children.backend.lock() {
            *slot = Some(backend_child);
        }
    }

    let backend_handle = handle.clone();
    let backend_shutdown = shutting_down.clone();
    let backend_exit_state = backend_exited.clone();
    let backend_log = startup_log.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = backend_events.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[backend] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    let line = String::from_utf8_lossy(&line);
                    eprintln!("[backend] {line}");
                    append_startup_log(&backend_log, &format!("[backend] {line}"));
                }
                CommandEvent::Terminated(status) if !backend_shutdown.load(Ordering::SeqCst) => {
                    backend_exit_state.store(true, Ordering::SeqCst);
                    eprintln!("[backend] unexpectedly terminated: {status:?}");
                    append_startup_log(
                        &backend_log,
                        &format!("[backend] unexpectedly terminated: {status:?}"),
                    );
                    if let Some(window) = backend_handle.get_webview_window("main") {
                        splash_status(
                            &window,
                            "The local ranking service stopped. Retry to restart SignalRank.",
                            true,
                        );
                    }
                    let _ = backend_handle.emit("signalrank-sidecar-exit", "backend");
                    break;
                }
                _ => {}
            }
        }
    });

    match wait_for_port(backend_port, Duration::from_secs(90), &backend_exited) {
        ServiceWait::Ready => {}
        ServiceWait::Exited => {
            return Err("The local ranking service exited before it became ready".into())
        }
        ServiceWait::TimedOut => {
            return Err("The local ranking service did not become ready within 90 seconds".into())
        }
    }
    let auth_secret = load_install_secret(&data_dir)?;

    startup_status(
        &handle,
        &startup_log,
        "Starting the local workspace interface…",
    );
    let web_exited = Arc::new(AtomicBool::new(false));

    let (mut web_events, web_child) = handle
        .shell()
        .sidecar("signalrank-web")?
        .current_dir(&resource_dir)
        .args([
            "--eval",
            "const parent=Number(process.env.SIGNALRANK_DESKTOP_PARENT_PID);\
             const timer=setInterval(()=>{try{process.kill(parent,0)}catch{process.exit(0)}},1000);\
             timer.unref();require(process.env.SIGNALRANK_WEB_SERVER)",
        ])
        .env("SIGNALRANK_WEB_SERVER", web_server)
        .env("SIGNALRANK_DESKTOP_PARENT_PID", &desktop_parent_pid)
        .env("HOSTNAME", "127.0.0.1")
        .env("PORT", web_port.to_string())
        .env("BACKEND_URL", &backend_url)
        .env("AUTH_URL", &web_url)
        .env("NEXTAUTH_URL", &web_url)
        .env("AUTH_SECRET", &auth_secret)
        .env("NEXTAUTH_SECRET", &auth_secret)
        .env(
            "NODE_OPTIONS",
            "--max-old-space-size=128 --max-semi-space-size=4",
        )
        .env("NODE_COMPILE_CACHE", data_dir.join("node-compile-cache"))
        .env("NEXT_TELEMETRY_DISABLED", "1")
        .env("SIGNALRANK_MODE", "desktop")
        .env("NEXT_PUBLIC_SIGNALRANK_MODE", "desktop")
        .env("SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN", bootstrap_token)
        .spawn()?;
    if let Some(children) = handle.try_state::<DesktopChildren>() {
        if let Ok(mut slot) = children.web.lock() {
            *slot = Some(web_child);
        }
    }

    let web_handle = handle.clone();
    let web_exit_state = web_exited.clone();
    let web_log = startup_log.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = web_events.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[web] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    let line = String::from_utf8_lossy(&line);
                    eprintln!("[web] {line}");
                    append_startup_log(&web_log, &format!("[web] {line}"));
                }
                CommandEvent::Terminated(status) if !shutting_down.load(Ordering::SeqCst) => {
                    web_exit_state.store(true, Ordering::SeqCst);
                    eprintln!("[web] unexpectedly terminated: {status:?}");
                    append_startup_log(
                        &web_log,
                        &format!("[web] unexpectedly terminated: {status:?}"),
                    );
                    if let Some(window) = web_handle.get_webview_window("main") {
                        splash_status(
                            &window,
                            "The local workspace interface stopped. Retry to restart SignalRank.",
                            true,
                        );
                    }
                    let _ = web_handle.emit("signalrank-sidecar-exit", "web");
                    break;
                }
                _ => {}
            }
        }
    });

    match wait_for_port(web_port, Duration::from_secs(60), &web_exited) {
        ServiceWait::Ready => {}
        ServiceWait::Exited => {
            return Err("The local workspace interface exited before it became ready".into())
        }
        ServiceWait::TimedOut => {
            return Err(
                "The local workspace interface did not become ready within 60 seconds".into(),
            )
        }
    }

    startup_status(&handle, &startup_log, "Opening your local workspace…");
    println!("[desktop] services ready backend={backend_url} web={web_url}");
    if let Some(window) = handle.get_webview_window("main") {
        clear_desktop_session_cookies(&window)?;
        window.eval(format!("window.location.replace({web_url:?})"))?;
    }

    if let Ok(seconds) = env::var("SIGNALRANK_SMOKE_EXIT_AFTER_READY") {
        if let Ok(seconds) = seconds.parse::<u64>() {
            let exit_handle = handle.clone();
            tauri::async_runtime::spawn(async move {
                thread::sleep(Duration::from_secs(seconds));
                exit_handle.exit(0);
            });
        }
    }
    Ok(())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            open_external,
            save_download,
            restart_app,
            reveal_startup_log
        ])
        .setup(setup_packaged_sidecars)
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                stop_sidecars(window.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build SignalRank desktop");

    app.run(|handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            stop_sidecars(handle);
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn service_wait_stops_immediately_after_child_exit() {
        let exited = AtomicBool::new(true);
        let started = Instant::now();

        let result = wait_for_port(9, Duration::from_secs(2), &exited);

        assert!(matches!(result, ServiceWait::Exited));
        assert!(started.elapsed() < Duration::from_millis(100));
    }

    #[test]
    fn service_wait_accepts_a_bound_loopback_port() {
        let listener = std::net::TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let exited = AtomicBool::new(false);

        let result = wait_for_port(port, Duration::from_secs(1), &exited);

        assert!(matches!(result, ServiceWait::Ready));
    }

    #[test]
    fn desktop_cookie_filter_is_scoped_to_signalrank() {
        assert!(is_desktop_session_cookie(
            "signalrank.desktop.session-token"
        ));
        assert!(is_desktop_session_cookie("signalrank.desktop.callback-url"));
        assert!(!is_desktop_session_cookie("next-auth.session-token"));
        assert!(!is_desktop_session_cookie("another-app.session-token"));
    }

    #[test]
    fn external_url_validation_accepts_only_safe_https_links() {
        assert!(validated_external_url("https://jobs.example.com/role?id=1").is_ok());
        for invalid in [
            "http://jobs.example.com/role",
            "javascript:alert(1)",
            "file:///tmp/role",
            "/relative-role",
            "https://user@jobs.example.com/role",
            "https://user:secret@jobs.example.com/role",
        ] {
            assert!(
                validated_external_url(invalid).is_err(),
                "accepted {invalid}"
            );
        }
    }
}

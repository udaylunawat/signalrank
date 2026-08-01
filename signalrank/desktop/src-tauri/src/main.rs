use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use tauri::webview::PageLoadEvent;
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

fn wait_for_port(port: u16, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if std::net::TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(150));
    }
    false
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

fn bundled_node_runtime(resource_dir: &Path) -> PathBuf {
    let mut runtime = resource_dir.join("node").join("signalrank-web");
    if cfg!(windows) {
        runtime.set_extension("exe");
    }
    runtime
}

fn startup_error(window: &tauri::WebviewWindow, message: &str) {
    let message = format!("Startup failed: {message}");
    let _ = window.eval(format!(
        "document.querySelector('.spinner')?.remove();\
         const status=document.querySelector('.status');\
         if(status){{status.textContent={message:?};status.style.color='#b42318';}}"
    ));
}

fn native_ui_smoke_script() -> &'static str {
    r#"(() => {
        const heading = Array.from(document.querySelectorAll('h1')).some((node) =>
            node.textContent?.includes('Rank jobs on this computer.')
        );
        const input = document.querySelector('#openrouter-key');
        const button = Array.from(document.querySelectorAll('button')).find((node) =>
            node.textContent?.includes('Validate and save')
        );
        if (input instanceof HTMLInputElement) {
            input.focus();
            input.value = 'native-ui-smoke';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        return JSON.stringify({
            pass: heading && input instanceof HTMLInputElement && !!button &&
                document.activeElement === input && input.value === 'native-ui-smoke',
            path: window.location.pathname,
        });
    })()"#
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
    let parsed = validate_external_url(&url)?;
    app.opener()
        .open_url(parsed.as_str(), None::<&str>)
        .map_err(|error| error.to_string())
}

fn validate_external_url(url: &str) -> Result<Url, String> {
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

    if env::var_os("SIGNALRANK_SMOKE_EXIT_AFTER_READY").is_some() {
        if let Some(window) = app.get_webview_window("main") {
            window.clear_all_browsing_data()?;
        }
    }

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
        )
        .await;
        if let Err(error) = result {
            eprintln!("[desktop] startup failed: {error}");
            if let Some(window) = handle.get_webview_window("main") {
                startup_error(&window, &error.to_string());
            }
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
) -> Result<(), Box<dyn std::error::Error>> {
    let backend_url = format!("http://127.0.0.1:{backend_port}");
    let web_url = format!("http://127.0.0.1:{web_port}");
    let resource_dir = handle.path().resource_dir()?;
    let server_js = find_server_js(&resource_dir.join("web"))?
        .ok_or("Bundled Next.js server.js was not found")?;
    let node_runtime = bundled_node_runtime(&resource_dir);
    if !node_runtime.is_file() {
        return Err("Bundled Node.js runtime was not found".into());
    }

    let (mut backend_events, backend_child) = handle
        .shell()
        .sidecar("signalrank-backend")?
        .env("HOST", "127.0.0.1")
        .env("PORT", backend_port.to_string())
        .env("SIGNALRANK_MODE", "desktop")
        .env("SIGNALRANK_APP_DATA_DIR", &data_dir)
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
    tauri::async_runtime::spawn(async move {
        while let Some(event) = backend_events.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[backend] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[backend] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(status) if !backend_shutdown.load(Ordering::SeqCst) => {
                    eprintln!("[backend] unexpectedly terminated: {status:?}");
                    let _ = backend_handle.emit("signalrank-sidecar-exit", "backend");
                    break;
                }
                _ => {}
            }
        }
    });

    if !wait_for_port(backend_port, Duration::from_secs(90)) {
        return Err("The local backend did not become ready".into());
    }
    let auth_secret = load_install_secret(&data_dir)?;

    let (mut web_events, web_child) = handle
        .shell()
        .command(node_runtime)
        .args([server_js.to_string_lossy().to_string()])
        .env("HOSTNAME", "127.0.0.1")
        .env("PORT", web_port.to_string())
        .env("BACKEND_URL", &backend_url)
        .env("AUTH_URL", &web_url)
        .env("NEXTAUTH_URL", &web_url)
        .env("AUTH_SECRET", &auth_secret)
        .env("NEXTAUTH_SECRET", &auth_secret)
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
    tauri::async_runtime::spawn(async move {
        while let Some(event) = web_events.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[web] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[web] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(status) if !shutting_down.load(Ordering::SeqCst) => {
                    eprintln!("[web] unexpectedly terminated: {status:?}");
                    let _ = web_handle.emit("signalrank-sidecar-exit", "web");
                    break;
                }
                _ => {}
            }
        }
    });

    if !wait_for_port(web_port, Duration::from_secs(60)) {
        return Err("The local web server did not become ready".into());
    }

    println!("[desktop] services ready backend={backend_url} web={web_url}");
    if let Some(window) = handle.get_webview_window("main") {
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
        .invoke_handler(tauri::generate_handler![open_external, save_download])
        .setup(setup_packaged_sidecars)
        .on_page_load(|webview, payload| {
            if env::var_os("SIGNALRANK_NATIVE_UI_SMOKE").is_none()
                || payload.event() != PageLoadEvent::Finished
                || payload.url().host_str() != Some("127.0.0.1")
            {
                return;
            }

            let webview = webview.clone();
            thread::spawn(move || {
                thread::sleep(Duration::from_millis(1500));
                let app_handle = webview.app_handle().clone();
                let callback_handle = app_handle.clone();
                if let Err(error) =
                    webview.eval_with_callback(native_ui_smoke_script(), move |result| {
                        let passed = result.contains("\\\"pass\\\":true")
                            || result.contains("\"pass\":true");
                        println!("[native-ui] smoke-result pass={passed} result={result}");
                        callback_handle.exit(if passed { 0 } else { 1 });
                    })
                {
                    eprintln!("[native-ui] smoke-eval failed: {error}");
                    app_handle.exit(1);
                }
            });
        })
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
    use super::{sanitized_filename, validate_external_url};

    #[test]
    fn sanitized_filename_removes_paths_and_unsafe_characters() {
        assert_eq!(sanitized_filename("../../roles:2026.csv"), "roles_2026.csv");
        assert_eq!(sanitized_filename("..."), "signalrank-export.csv");
    }

    #[test]
    fn external_url_policy_accepts_https_without_credentials() {
        let parsed = validate_external_url("https://jobs.example.test/role").unwrap();
        assert_eq!(parsed.scheme(), "https");
    }

    #[test]
    fn external_url_policy_rejects_non_https_and_credentials() {
        for value in [
            "http://jobs.example.test/role",
            "file:///tmp/role.csv",
            "javascript:alert(1)",
            "/relative/path",
            "https://user:password@jobs.example.test/role",
        ] {
            assert!(validate_external_url(value).is_err(), "accepted {value}");
        }
    }
}

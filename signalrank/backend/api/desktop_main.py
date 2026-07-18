import multiprocessing
import os
import sys
import threading
import time


def _desktop_parent_pid() -> int | None:
    value = os.getenv("SIGNALRANK_DESKTOP_PARENT_PID", "").strip()
    try:
        pid = int(value)
    except ValueError:
        return None
    return pid if pid > 1 else None


def _process_is_running(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            return bool(
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ) and (exit_code.value == still_active)
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _exit_when_desktop_parent_stops() -> None:
    parent_pid = _desktop_parent_pid()
    if parent_pid is None:
        return

    def monitor() -> None:
        while True:
            if not _process_is_running(parent_pid):
                os._exit(0)
            time.sleep(1)

    threading.Thread(target=monitor, name="desktop-parent-watch", daemon=True).start()


def main() -> None:
    os.environ.setdefault("SIGNALRANK_MODE", "desktop")
    _exit_when_desktop_parent_stops()
    bundle_dir = getattr(sys, "_MEIPASS", "")
    if bundle_dir:
        os.environ["PATH"] = bundle_dir + os.pathsep + os.environ.get("PATH", "")

    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

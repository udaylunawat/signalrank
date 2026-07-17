import multiprocessing
import os
import sys


def main() -> None:
    os.environ.setdefault("SIGNALRANK_MODE", "desktop")
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

# embeddings/telemetry.py
import time
from contextlib import contextmanager


@contextmanager
def log_timer(logger, label: str):
    start = time.perf_counter()
    yield
    elapsed = (time.perf_counter() - start) * 1000
    if logger:
        logger.info(f"[EMBED] {label} took {elapsed:.1f} ms")

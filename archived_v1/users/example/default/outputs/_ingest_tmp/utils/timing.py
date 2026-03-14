import time
from contextlib import contextmanager


@contextmanager
def timed(label, logger):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logger.info(f"[TIME] {label} took {elapsed:.2f}s")

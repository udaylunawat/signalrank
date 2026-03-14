import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("proxy-test")


TEST_URL = "https://example.com"   # safe lightweight target
TIMEOUT = 3                       # seconds
MAX_WORKERS = 50                  # parallelism


def load_proxies(path="proxies.txt"):
    p = Path(path)
    proxies = []

    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "://" not in line:
            line = "http://" + line
        proxies.append(line)

    return proxies


def test_proxy(proxy_url: str):
    proxies = {"http": proxy_url, "https": proxy_url}

    start = time.time()
    try:
        r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        elapsed = time.time() - start
        return proxy_url, True, elapsed, r.status_code
    except Exception:
        elapsed = time.time() - start
        return proxy_url, False, elapsed, None


def main():
    proxies = load_proxies("proxies.txt")
    logger.info("Loaded %d proxies", len(proxies))

    working = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(test_proxy, p) for p in proxies]

        for fut in as_completed(futures):
            proxy, ok, elapsed, status = fut.result()

            if ok:
                logger.info("OK   %s (%.2fs, status=%s)", proxy, elapsed, status)
                working.append((proxy, elapsed))
            else:
                logger.info("FAIL %s (%.2fs)", proxy, elapsed)

    working.sort(key=lambda x: x[1])

    out = Path("working_proxies.txt")
    out.write_text("\n".join([p for p, _ in working]) + "\n")

    logger.info("Working proxies: %d", len(working))
    logger.info("Saved to %s", out)


if __name__ == "__main__":
    main()
import logging
from typing import Callable, Optional


class StreamlitLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        msg = self.format(record)
        self.callback(msg)


def setup_logger(
    streamlit_callback: Optional[Callable[[str], None]] = None,
    debug: bool = False,
):
    """
    Canonical logger factory.
    NEVER redefine this elsewhere.
    """
    logger = logging.getLogger("jobs")
    logger.handlers.clear()

    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    formatter = logging.Formatter("[%(levelname)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if streamlit_callback:
        handler = StreamlitLogHandler(streamlit_callback)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
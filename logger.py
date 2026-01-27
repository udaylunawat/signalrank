# ================================
# FILE: logger.py
# ================================
import logging
from typing import Callable, Optional

from config_loader import settings


class StreamlitLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        msg = self.format(record)
        self.callback(msg)


def setup_logger(
    streamlit_callback: Optional[Callable[[str], None]] = None,
):
    """
    Canonical logger factory.
    Configuration comes from settings.yaml.
    """
    logger = logging.getLogger("jobs")
    logger.handlers.clear()

    level = getattr(logging, settings.logging.level, logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(settings.logging.format)

    # Console
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Optional file logging
    if settings.logging.log_to_file:
        file_handler = logging.FileHandler(settings.logging.log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Optional Streamlit hook
    if streamlit_callback:
        handler = StreamlitLogHandler(streamlit_callback)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
import logging


class StreamlitLogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        msg = self.format(record)
        self.callback(msg)


def setup_logger(streamlit_callback=None):
    logger = logging.getLogger("jobs")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("[%(levelname)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if streamlit_callback:
        st_handler = StreamlitLogHandler(streamlit_callback)
        st_handler.setFormatter(formatter)
        logger.addHandler(st_handler)

    return logger
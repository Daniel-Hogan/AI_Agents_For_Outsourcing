import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()

    # Avoid duplicate handlers if configure_logging is called multiple times.
    if root.handlers:
        root.setLevel(level.upper())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root.addHandler(handler)
    root.setLevel(level.upper())

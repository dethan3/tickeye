"""Logging configuration shared by all application entry points."""

import logging


def configure_logging(*, debug: bool) -> None:
    """Configure predictable console logging without leaking request payloads."""

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

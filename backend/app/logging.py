"""Journaux structurés avec structlog.

- En développement : journaux colorés et lisibles dans le terminal.
- Ailleurs : une ligne JSON par événement, facile à indexer dans Loki
  (outil de centralisation des journaux mis en place à l'étape 5).
"""

import logging

import structlog

from app.config import get_settings


def configure_logging() -> None:
    is_dev = get_settings().environment == "development"
    renderer: structlog.typing.Processor = (
        structlog.dev.ConsoleRenderer() if is_dev else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

"""Configuración de logging compartida por las fases ejecutables.

Escribe a consola y a `logs/scrape.log` (UTF-8, append). Se llama una vez al
inicio de cada módulo `python -m src.<modulo>`.
"""

from __future__ import annotations

import logging

from src import config


def setup_logging(level: int = logging.INFO) -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("unam-scraper")
    if root.handlers:  # ya configurado (evita duplicar handlers)
        return
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.FileHandler(
        config.LOG_PATH, mode="a", encoding=config.ENCODING
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

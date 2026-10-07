"""Configuración centralizada de logging para todo el backend."""
import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """Configura un formato de logging consistente para toda la aplicación.

    Se llama una única vez al iniciar la aplicación (ver app/main.py).
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

# src/utils/logging_config.py — Logging estruturado em JSON para o Trend Radar

import logging
import sys

try:
    from pythonjsonlogger.json import JsonFormatter as _JsonFormatter
except ImportError:  # python-json-logger < 3.x
    from pythonjsonlogger.jsonlogger import JsonFormatter as _JsonFormatter  # type: ignore[no-redef]


def setup_logging(level: int = logging.INFO) -> None:
    """Configura o root logger com saída JSON estruturada para stdout.

    Chame uma vez na entrada de cada módulo principal (DAGs, scripts, API).
    Campos emitidos em cada linha:
        asctime, name, levelname, message + quaisquer campos extras passados
        via logger.info('msg', extra={...}).

    Exemplo de saída:
        {"asctime": "2026-04-14T06:00:00", "name": "src.ingestion.lastfm_client",
         "levelname": "INFO", "message": "ingestion_completed",
         "source": "lastfm", "records_inserted": 148, "duration_ms": 4231}
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = _JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Silencia loggers muito verbosos de dependências
    for noisy in ("httpx", "httpcore", "googleapiclient", "urllib3",
                  "cmdstanpy", "prophet"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

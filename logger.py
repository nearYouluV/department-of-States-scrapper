import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("/app/logs")  # volume з docker-compose
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("app_logger")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# INFO handler (тільки до ERROR)
info_handler = RotatingFileHandler(
    LOG_DIR / "logs.log",
    maxBytes=5_000_000,
    backupCount=5
)
info_handler.setLevel(logging.INFO)

class MaxInfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR

info_handler.addFilter(MaxInfoFilter())
info_handler.setFormatter(formatter)

# ERROR handler
error_handler = RotatingFileHandler(
    LOG_DIR / "errors.log",
    maxBytes=5_000_000,
    backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# Console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)

logger.propagate = False

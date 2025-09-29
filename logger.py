import logging
from logging.handlers import RotatingFileHandler


logger = logging.getLogger("app_logger")
logger.setLevel(logging.DEBUG)


formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


info_handler = RotatingFileHandler("logs.log", maxBytes=5_000_000, backupCount=5)
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(formatter)

class MaxInfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR

info_handler.addFilter(MaxInfoFilter())

error_handler = RotatingFileHandler("errors.log", maxBytes=5_000_000, backupCount=5)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)

logger.propagate = False

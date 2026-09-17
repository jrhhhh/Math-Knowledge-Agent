import json
import logging
import os
from logging.handlers import RotatingFileHandler

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname,
                           "logger": record.name, "message": record.getMessage()}, ensure_ascii=False)

def configure_logging():
    logger = logging.getLogger("math_agent")
    if logger.handlers:
        return logger
    logger.setLevel(os.getenv("MATH_AGENT_LOG_LEVEL", "INFO").upper())
    formatter = JsonFormatter()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    path = os.getenv("MATH_AGENT_LOG_FILE", "math_agent.log")
    file_handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger

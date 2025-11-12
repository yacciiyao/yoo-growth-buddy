# logging_config.py
import logging
from logging.handlers import TimedRotatingFileHandler
import os

from app.settings import settings


def setup_logging():
    # 获取日志存储路径
    log_dir = settings.LOGS_PATH
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 创建日志记录器
    logger = logging.getLogger("smart-buddy")
    logger.setLevel(logging.DEBUG)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # 创建定时轮转的文件处理器，按天生成日志文件
    log_file_path = os.path.join(log_dir, "app.log")
    file_handler = TimedRotatingFileHandler(
        log_file_path, when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)

    # 创建日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

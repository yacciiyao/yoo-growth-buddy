# -*- coding: utf-8 -*-
# @File: ylogger.py
# @Author: yaccii
# @Time: 2025-11-07 11:46
# @Description:
import logging


def setup_logger(name: str = "Growth-Buddy", level=logging.INFO):
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s - %(message)s]',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger


# 全局日志实例
ylogger = setup_logger()

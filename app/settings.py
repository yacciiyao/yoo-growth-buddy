# -*- coding: utf-8 -*-
# Author: yaccii.yao
# Date: 2025/2/26
# Description:
import os

from dotenv import load_dotenv
from pydantic.v1 import BaseSettings


class Settings(BaseSettings):
    load_dotenv()
    XFYUN_APPID = os.getenv("XFYUN_APPID")
    XFYUN_APISecret = os.getenv("XFYUN_APISECRET")
    XFYUN_APIKey = os.getenv("XFYUN_APIKEY")

    OPENAI_APIKey = os.getenv("OPENAI_APIKEY")

    DeepSeek_APIKey = os.getenv("DeepSeek_APIKEY")
    DeepSeek_BaseUrl = os.getenv("DeepSeek_BaseUrl")

    BOT_NAME = "smart-buddy"
    cur_path = os.path.abspath(os.path.dirname(__file__))
    PROJECT_PATH = (cur_path[:cur_path.find('{}'.format(BOT_NAME))] + '{}\\'.format(BOT_NAME)).replace("\\", '/')
    File_PATH = os.path.join(PROJECT_PATH, "files").replace(os.sep, '/')
    LOGS_PATH = os.path.join(PROJECT_PATH, 'logs')
    DEBUG = True
    ENV = "dev"


settings = Settings()
import base64
import hashlib
import hmac
import json
import logging
import ssl
import threading
import time
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websocket

from app.settings import settings

STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

logger = logging.getLogger("smart-buddy")


class SpeechRecognitionService(object):
    # 初始化
    def __init__(self):
        self.APPID = settings.XFYUN_APPID
        self.APIKey = settings.XFYUN_APIKey
        self.APISecret = settings.XFYUN_APISecret

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，更多个性化参数可在官网查看
        self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo": 1, "vad_eos": 10000}

    # 生成url
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'

        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }

        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)

        return url

    def on_message(self, ws, message):
        try:
            code = json.loads(message)["code"]
            sid = json.loads(message)["sid"]
            if code != 0:
                err_msg = json.loads(message)["message"]
                logger.error(f"SpeechRecognitionService: (sid: {sid}, err_msg: {err_msg}, code: {code})")

            else:
                data = json.loads(message)["data"]["result"]["ws"]
                for i in data:
                    for w in i["cw"]:
                        ws.result += w["w"]

        except Exception as e:
            logger.error(f"SpeechRecognitionService exception: {e}")

    def on_error(self, ws, error):
        logger.error(f"SpeechRecognitionService error: {error}")

    def on_close(self, ws, a, b):
        logger.info(f"SpeechRecognitionService closed")

    def on_open(self, ws, audio_file):
        def run(*args):
            frame_size = 8000  # 每一帧的音频大小
            interval = 0.04  # 发送音频间隔(单位:s)
            status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧

            with open(audio_file, "rb") as fp:
                while True:
                    buf = fp.read(frame_size)
                    # 文件结束
                    if not buf:
                        status = STATUS_LAST_FRAME
                    # 第一帧处理
                    if status == STATUS_FIRST_FRAME:
                        d = {"common": self.CommonArgs,
                             "business": self.BusinessArgs,
                             "data": {"status": 0, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'),
                                      "encoding": "raw"}}
                        d = json.dumps(d)
                        ws.send(d)
                        status = STATUS_CONTINUE_FRAME
                    # 中间帧处理
                    elif status == STATUS_CONTINUE_FRAME:
                        d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'),
                                      "encoding": "raw"}}
                        ws.send(json.dumps(d))
                    # 最后一帧处理
                    elif status == STATUS_LAST_FRAME:
                        d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'),
                                      "encoding": "raw"}}
                        ws.send(json.dumps(d))
                        time.sleep(1)
                        break
                    # 模拟音频采样间隔
                    time.sleep(interval)
                ws.close()

        threading.Thread(target=run).start()

    def recognize(self, audio_input):
        ws = websocket.WebSocketApp(self.create_url(), on_message=self.on_message, on_error=self.on_error,
                                    on_close=self.on_close)
        ws.result = ""  # 接收解析结果
        ws.on_open = lambda ws: self.on_open(ws, audio_input)
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        return ws.result

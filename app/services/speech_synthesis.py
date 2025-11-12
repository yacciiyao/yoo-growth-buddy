import base64
import hashlib
import hmac
import json
import logging
import os
import ssl
import tempfile
import threading
import time
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import certifi
import websocket

from app.settings import settings
from app.utils.audio_converter import convert_to_wav, convert_to_mp3

logger = logging.getLogger("smart-buddy")


class Status:
    """WebSocket 状态常量"""
    FIRST_FRAME = 0
    CONTINUE_FRAME = 1
    LAST_FRAME = 2


class SpeechSynthesisService:
    def __init__(self):
        # 基础认证信息
        self.APPID = settings.XFYUN_APPID
        self.APIKey = settings.XFYUN_APIKey
        self.APISecret = settings.XFYUN_APISecret

        # 业务参数配置
        self.business_params = {
            "aue": "raw",
            "auf": "audio/L16;rate=16000",
            "vcn": "xiaoyan",
            "tte": "utf8",
            "speed": 80,
            "volume": 30,
        }

        # SSL配置
        self.sslopt = {
            "cert_reqs": ssl.CERT_REQUIRED if settings.ENV == 'production' else ssl.CERT_NONE,
            "ca_certs": certifi.where() if settings.ENV == 'production' else None
        }

    def create_url(self):
        """构建WebSocket连接URL"""
        host = "ws-api.xfyun.cn"
        path = "/v2/tts"
        url = f"wss://{host}{path}"

        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(
            self.APISecret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode('utf-8')

        authorization_origin = (
            f'api_key="{self.APIKey}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature_sha}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        params = {
            "authorization": authorization,
            "date": date,
            "host": host
        }
        return f"{url}?{urlencode(params)}"

    def on_message(self, ws, message, pcm_path, completion_event):
        """WebSocket消息回调"""
        try:
            message = json.loads(message)

            code = message.get("code", -1)
            sid = message.get("sid", "unknown")
            status = message.get("data", {}).get("status", -1)

            if code != 0:
                err_msg = message.get("message", "Unknown error")
                logger.error(f"Synthesis failed (sid: {sid}): {err_msg} [code: {code}]")
                ws.close()
                completion_event.set()
                return

            if status == Status.LAST_FRAME:
                logger.info(f"Received final frame (sid: {sid})")
                completion_event.set()
                return  # 不要立即关闭连接，等待服务端关闭

            if "data" in message and "audio" in message["data"]:
                audio_data = base64.b64decode(message["data"]["audio"])
                try:
                    with open(pcm_path, 'ab') as f:
                        f.write(audio_data)
                    logger.debug(f"Appended {len(audio_data)} bytes to {pcm_path}")
                except IOError as e:
                    logger.error(f"Failed to write audio data: {e}")
                    completion_event.set()

        except Exception as e:
            logger.error(f"Message handling error: {str(e)}")
            completion_event.set()

    def on_error(self, ws, error):
        """WebSocket错误回调"""
        logger.error(f"WebSocket error: {str(error)}")

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket关闭回调"""
        logger.info(f"Connection closed: code={close_status_code}, message={close_msg or 'no message'}")

    def on_open(self, ws, text, pcm_path, completion_event):
        """WebSocket连接打开回调"""

        def run():
            try:
                request_data = {
                    "common": {"app_id": self.APPID},
                    "business": self.business_params,
                    "data": {
                        "status": 2,
                        "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
                    }
                }
                ws.send(json.dumps(request_data))
                logger.debug(f"Sent synthesis request: {json.dumps(request_data, indent=2)}")
            except Exception as e:
                logger.error(f"Failed to send request: {str(e)}")
                completion_event.set()

        threading.Thread(target=run, name="WebSocketSender").start()

    def synthesis(self, text, output_path, max_retries=3, timeout=30):
        """执行语音合成

        :param text: 需要合成的文本
        :param output_path: 输出文件路径
        :param max_retries: 最大重试次数
        :param timeout: 超时时间（秒）
        :return: 是否成功
        """
        for attempt in range(1, max_retries + 1):
            try:
                return self._perform_synthesis(text, output_path, timeout)
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {str(e)}")
                if attempt == max_retries:
                    logger.error("All attempts failed")
                    return False
                time.sleep(2 ** attempt)
        return False

    def _perform_synthesis(self, text, output_path, timeout):
        """实际执行合成逻辑"""
        websocket.enableTrace(False)
        completion_event = threading.Event()

        pcm_path = os.path.join(settings.File_PATH, f"temp_{int(time.time())}.pcm").replace(os.sep, '/')

        ws = None
        ws_thread = None
        try:
            # 初始化WebSocket连接
            ws = websocket.WebSocketApp(
                self.create_url(),
                on_message=lambda ws, msg: self.on_message(ws, msg, pcm_path, completion_event),
                on_error=self.on_error,
                on_close=self.on_close
            )
            ws.on_open = lambda ws: self.on_open(ws, text, pcm_path, completion_event)

            # 启动连接线程
            ws_thread = threading.Thread(
                target=ws.run_forever,
                kwargs={"sslopt": self.sslopt},
                name="WebSocketThread"
            )
            ws_thread.start()

            # 等待完成或超时
            if not completion_event.wait(timeout):
                raise TimeoutError(f"Operation timed out after {timeout} seconds")

            # 等待WebSocket线程结束
            ws_thread.join(timeout=5)
            if ws_thread.is_alive():
                logger.warning("WebSocket thread did not terminate gracefully")

            # 验证生成文件
            self._validate_pcm_file(pcm_path)

            # 转换文件格式
            output_format = self._get_output_format(output_path)

            # 使用文件路径进行转换
            logger.info(f"Starting audio conversion to {output_format}")
            if output_format == 'mp3':
                convert_to_mp3(pcm_path, output_path)
            else:
                convert_to_wav(pcm_path, output_path)

            logger.info(f"Successfully generated: {output_path}")
            return True

        finally:
            # 清理资源
            if ws:
                ws.close()
            if ws_thread and ws_thread.is_alive():
                ws_thread.join(timeout=2)
            self._cleanup_temp_file(pcm_path)

    def _validate_pcm_file(self, pcm_path):
        """验证PCM文件完整性"""
        logger.debug(f"Validating PCM file: {pcm_path}")
        if not os.path.exists(pcm_path):
            raise FileNotFoundError(f"PCM file not found at {pcm_path}")

        file_size = os.path.getsize(pcm_path)
        logger.debug(f"PCM file size: {file_size} bytes")

        if file_size == 0:
            raise ValueError("Generated PCM file is empty")

        # 添加基础文件头验证（可选）
        with open(pcm_path, 'rb') as f:
            header = f.read(4)
            if len(header) < 4:
                raise ValueError("Invalid PCM file header")

    def _get_output_format(self, output_path):
        """获取输出文件格式"""
        output_format = output_path.split('.')[-1].lower()
        if output_format not in ('wav', 'mp3'):
            raise ValueError(f"Unsupported format: {output_format}")
        return output_format

    def _cleanup_temp_file(self, pcm_path):
        """清理临时文件"""
        if os.path.exists(pcm_path):
            try:
                os.remove(pcm_path)
                logger.debug(f"Removed temporary file: {pcm_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temp file: {str(e)}")
        else:
            logger.debug(f"Temporary file {pcm_path} does not exist")
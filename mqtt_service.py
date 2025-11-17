# -*- coding: utf-8 -*-
# @File: mqtt_service.py
# @Author: yaccii
# @Time: 2025-11-17 16:45
# @Description:
# run_mqtt_gateway.py
from __future__ import annotations

import logging

from app.mqtt.gateway import MqttVoiceGateway

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

if __name__ == "__main__":
    gateway = MqttVoiceGateway()
    gateway.start()

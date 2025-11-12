import json
import paho.mqtt.client as mqtt
import os
import warnings
import time
import base64  # Import base64 for encoding binary data

warnings.filterwarnings("ignore", category=DeprecationWarning)

# MQTT 配置
MQTT_BROKER = "127.0.0.1"  # MQTT 服务的主机（本地服务）
MQTT_PORT = 1883          # MQTT 服务的端口
MQTT_TOPIC_IN = "chat/audio/in"  # 发送音频文件的主题
MQTT_TOPIC_OUT = "chat/audio/out"  # 接收音频文件的主题
MQTT_CLIENT_ID = f"publisher-client-{os.getpid()}"  # 发布者客户端 ID，使用进程ID防止冲突

session_id = None  # 初始时没有 session_id

# 连接回调函数
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"连接成功，返回码 {rc}")
    # 连接成功后订阅响应主题
    client.subscribe(MQTT_TOPIC_OUT)
    # 开始发布音频文件
    send_audio_file(client)

# 发布回调函数
def on_publish(client, userdata, mid):
    print(f"消息已发布，消息 ID：{mid}")

# 消息接收回调函数
def on_message(client, userdata, msg):
    global session_id
    print("Received audio and response data")
    try:
        # 解析消息
        message = json.loads(msg.payload)

        response_session_id = message.get("session_id")
        audio_data_base64 = message.get("audio_reply")
        filename = message.get("filename")
        text_reply = message.get("text_reply")

        if not audio_data_base64:
            print("错误: 返回数据中缺少 audio_reply")
            return

        # 如果没有 session_id，首次响应时获取并设置 session_id
        if session_id is None and response_session_id:
            session_id = response_session_id
            print(f"首次请求返回 session_id: {session_id}")

        # 解码音频数据
        audio_data = base64.b64decode(audio_data_base64)

        # 生成唯一的文件名并保存音频文件
        audio_file_path = os.path.join('./received', filename)
        with open(audio_file_path, 'wb') as f:
            f.write(audio_data)
        print(f"音频文件已保存: {audio_file_path}")

        # 打印文本回复
        print(f"文本回复：{text_reply}")

        # 等待下一轮发送
        send_audio_file(client)

    except Exception as e:
        print(f"Error receiving audio and data: {e}")

# 创建 MQTT 客户端，指定使用 MQTTv5 协议
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)

# 设置回调函数
mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish
mqtt_client.on_message = on_message

# 连接到 MQTT 代理
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

# 读取并发送音频文件
def send_audio_file(client):
    global session_id
    file_path = "./source/promax.m4a"  # 请替换为实际的音频文件路径

    # 如果 session_id 为空，表示首次发送
    if session_id is None:
        session_id = ""  # 初次时空的 session_id

    # 确保文件路径存在
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return

    try:
        with open(file_path, "rb") as file:
            file_data = file.read()  # 读取音频文件的二进制数据
            file_data_base64 = base64.b64encode(file_data).decode('utf-8')  # 编码为Base64字符串

            message = {
                "audio_data": file_data_base64,
                "metadata": {
                    "filename": os.path.basename(file_path),
                    "size": len(file_data)
                },
                "session_id": session_id  # 将 session_id 添加到消息中
            }
            # 将音频数据封装在一个JSON消息中
            result = client.publish(MQTT_TOPIC_IN, json.dumps(message))  # 发布到指定的 MQTT 主题
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"消息发布失败，返回码: {result.rc}")
            else:
                print(f"文件已成功发布，session_id: {session_id}")
    except Exception as e:
        print(f"文件发送失败: {e}")

# 启动 MQTT 客户端循环，等待连接和回调
mqtt_client.loop_start()  # 启动客户端的 MQTT 循环

# 保证脚本持续运行，直到连接成功并发布消息
while not mqtt_client.is_connected():
    print("等待连接...")
    time.sleep(1)

print("MQTT 客户端已连接，准备发布文件。")

# 添加 input() 保持脚本运行，等待服务端的响应
input("按 Enter 键退出程序...\n")

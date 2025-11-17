# Yoo Growth Buddy

Yoo Growth Buddy 是一个面向 3–12 岁儿童的 **智能语音陪伴玩具后端系统**，
支持多轮对话、语音交互、安全审计和会话记录查询，
适合作为个人项目或实际产品原型。

---

## 功能概览

### 1. 语音对话链路（玩具端 ⇄ 后端）

- 终端通过 **MQTT** 将采集到的儿童语音（16kHz / 16bit / mono WAV）发送到后端：  
  `toy/{device_sn}/voice/request`
- 后端 MQTT 网关接收消息并调用 `VoiceChatService`：
  1. 根据 `device_sn` 查找并校验绑定的儿童信息；
  2. 将语音通过 **讯飞 ASR** 转换为中文文本；
  3. 调用 **大模型服务（DeepSeek 等）** 生成回复文本；
  4. 对回复文本做内容安全收敛（不合规则替换为安全引导语）；
  5. 使用 **讯飞 TTS** 将回复文本合成为语音（PCM → WAV）；
  6. 将回复语音通过 MQTT 发送回终端：  
     `toy/{device_sn}/voice/reply`
- 每一轮对话（Turn）的**文本和语音元数据**都会落库，并将音频文件上传到 **S3 兼容对象存储**。

### 2. 家长管理 & 配置

通过 HTTP API，家长可以：

- **初始化绑定**：创建家长、孩子和设备，并完成 1:1 绑定；
- **配置玩具人设**：包括玩具名称、性别、年龄、性格描述（persona）；
- **配置儿童信息**：姓名、年龄、性别、兴趣爱好、禁止话题等。

这些信息会在调用大模型时转化为系统提示（system prompt），用于定制化小助手的行为。

### 3. 历史会话 & 风险监控

- 家长可以查询 **某个孩子的会话列表**：
  - 会话起止时间（基于 Turn 时间戳推断）；
  - 轮次数量；
  - 最近一轮对话的用户文本 & 回复文本；
  - 是否存在风险对话以及风险轮次统计。
- 家长可以查看 **单次会话详情**：
  - 每一轮的：
    - 文本（孩子 → 小yo）；
    - 语音访问 URL（存储于 S3）；
    - 风险标记（是否风险、来源、原因）。

> 设计原则：
> - **孩子说的“不安全内容”会保留**，以便家长及时发现；  
> - **模型回复的部分会经过安全收敛**，不保存不合规回复，只保存经过收敛后的安全文本。

---

## 技术栈与架构

### 核心技术

- **后端框架**：FastAPI
- **数据库**：MySQL + SQLAlchemy ORM
- **消息通道**：MQTT（例如 Mosquitto）
- **语音服务**：
  - ASR：科大讯飞语音识别（WebSocket）
  - TTS：科大讯飞语音合成（WebSocket）
- **大模型接入**：
  - DeepSeek Chat（兼容 OpenAI SDK）
  - 预留 OpenAI / Qwen 等接入能力
- **对象存储**：
  - 任意 S3 兼容存储（AWS S3 / Cloudflare R2 / MinIO / Backblaze B2 等）
- **配置管理**：Pydantic Settings + `.env`

### 目录结构（简化版）

```text
yoo-growth-buddy/
  app/
    api/
      parents.py        # 家长 / 儿童 / 设备初始化与配置
      history.py        # 家长侧对话历史查询
      deps.py           # FastAPI 依赖注入（DB、Service 等）

    domain/
      models.py         # SQLAlchemy ORM 模型（Parent / Child / Device / ChatSession / Turn 等）
      schemas.py        # 领域层数据结构（业务用 DTO / VO）
      safety.py         # 文本内容安全检测与标记逻辑

    infra/
      config.py         # 读取 .env，统一配置
      db.py             # 数据库引擎、Session 工厂
      storage_s3.py     # S3 兼容对象存储上传 & URL 生成

    llm/
      base.py           # LLM Provider 协议（接口定义）
      deepseek.py       # DeepSeek 具体实现（基于 openai.Client）
      __init__.py       # 模型注册表 & LlmModelSelector

    speech/
      asr_xfyun.py      # 讯飞 ASR 客户端（WebSocket）
      tts_xfyun.py      # 讯飞 TTS 客户端（WebSocket）
      client.py         # SpeechClient 统一封装（对外提供 asr / tts 异步接口）

    mqtt/
      gateway.py        # MQTT 网关：订阅 toy/{sn}/voice/request，发布 toy/{sn}/voice/reply

    services/
      profile_service.py    # 家长/孩子/设备配置相关业务
      voice_chat_service.py # 核心语音多轮对话业务逻辑
      history_service.py    # 历史会话查询业务逻辑

    main.py             # FastAPI 入口应用（挂载路由、CORS、生命周期等）

  client.py             # 本地 MQTT 测试客户端（模拟“玩具端”，发送 WAV，接收回复）
  mqtt_service.py       # 启动 MQTT 网关的脚本
  init_db.py            # 初始化数据库表结构
  init_data.py          # 插入一些测试数据（家长/孩子/设备）
  requirements.txt      # Python 依赖
  .env                  # 环境变量配置（不提交到仓库）
```

---

## 运行流程

以下步骤假设你已经安装好 Python 3.10+ 且处于项目根目录。

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并根据实际情况填写：

- 数据库配置：`DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- DeepSeek：`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`
- 讯飞：`XFYUN_APPID` / `XFYUN_APIKEY` / `XFYUN_APISECRET`
- S3：`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_REGION` / `AWS_S3_BUCKET` / `AWS_S3_BASE_URL`
- MQTT：`MQTT_BROKER_HOST` / `MQTT_BROKER_PORT` / `MQTT_USERNAME` / `MQTT_PASSWORD`

### 3. 初始化数据库

```bash
python init_db.py
```

如需测试数据（家长 / 孩子 / 设备绑定等），执行：

```bash
python init_data.py
```

### 4. 启动 FastAPI HTTP 服务

```bash
uvicorn app.main:app --reload --port 8000
```

默认将提供以下主要接口：

- `POST /api/parents/setup` – 家长初始化绑定孩子和设备
- `GET  /api/history/children/{child_id}/sessions` – 会话列表
- `GET  /api/history/sessions/{session_id}/turns` – 单次会话详情

你可以通过 Swagger UI 访问：  
`http://127.0.0.1:8000/docs`

### 5. 启动 MQTT 网关

确保本地或远程已有 MQTT Broker（例如 Mosquitto）监听在 `.env` 中配置的地址。然后执行：

```bash
python mqtt_service.py
```

MQTT 网关会：

- 订阅：`toy/+/voice/request`
- 发布：`toy/{device_sn}/voice/reply`

### 6. 使用客户端脚本模拟“玩具端”

准备一段 **16kHz 单声道 16bit WAV** 文件（如 `toy/request/test_input_1.wav`），然后执行：

```bash
python client.py   --host 127.0.0.1   --port 1883   --device-sn abc1244   --input-wav ./toy/request/test_input_1.wav   --output-dir ./toy/reply
```

- `device-sn` 需要和数据库中初始化绑定的设备序列号一致；
- 成功后，会在 `output-dir` 中生成形如 `reply_abc1244_XXXXXXXXXX.wav` 的回复音频文件。

---

## 安全策略与风控逻辑（简要说明）

- 所有进入大模型前后的文本都会经过 `domain/safety.py` 中的规则检测；
- 对于孩子端文本：  
  - 如果包含敏感 / 危险内容（例如自伤、自杀、严重暴力、家长禁止的话题等），
    会在 `Turn` 中记录 `risk_flag=1` 以及 `risk_source="user"`、`risk_reason`；
- 对于模型回复文本：
  - 一旦检测到风险内容，不会将这一版本直接返回，而是统一替换为一段**安全的引导话术**；
  - DB 中只保留收敛后的安全版本。

家长可以通过历史接口查看哪些轮次存在风险，便于对孩子做及时的干预和关爱。

---

## 可扩展方向

- **多模型路由 / A/B 实验**：
  - 根据孩子年龄段、会话类型、风险等级，自动在不同大模型之间路由；
  - 支持埋点对话质量评分，为后续模型对比实验和优化提供基础。

- **内容审核增强**：
  - 引入更精细的审核标签（情绪识别、欺凌检测等），为家长提供更全面的成长报告。

- **家长控制台**：
  - 为家长提供 Web 控制台：查看孩子使用时长、主题偏好、风险聚类情况等。

- **设备侧优化**：
  - 支持断线重试、消息重发、QoS 等，增强 IoT 场景的鲁棒性。

---

## 许可

本项目默认以 MIT 协议开源（可根据你自己的实际情况修改）。

```text
MIT License
```

欢迎用于学习和个人使用。

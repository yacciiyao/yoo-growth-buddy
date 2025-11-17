# Yoo Growth Buddy

Yoo Growth Buddy 是一个面向 3–12 岁儿童的 **智能语音陪伴玩具后端系统**，
支持多轮对话、语音交互、安全审计和会话记录查询，
既可以作为个人项目，也可以演化为实际产品原型。

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
- 每一轮对话（Turn）的 **文本和语音元数据** 都会落库，并将音频文件上传到 **S3 兼容对象存储**。

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
  - 是否存在风险对话。

- 家长可以查看 **单次会话详情**：
  - 每一轮的：
    - 文本（孩子 → 小yo）；
    - 语音访问 URL（存储于 S3）；
    - 风险标记（是否风险、来源、原因）。

> 策略：
> - 孩子说的“不安全内容”会保存，用于家长监控；  
> - 模型回复会做安全收敛，不保存不合规回复，只保存收敛后的安全版本。

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
  .env.example          # 环境变量模板文件（提交到 Git）
  .env                  # 本地环境变量配置（不要提交）
```

---

## 环境变量配置
 
将 `.env.example` 复制为 `.env` 并按你的环境修改具体值：

```bash
cp .env.example .env   # Windows 可直接复制文件
```

建议的 `.env.example` 字段如下（根据当前代码整理）：

### 基础信息

```env
ENV=dev
APP_NAME="Yoo Growth Buddy"
APP_VERSION=0.2.0
```

### 数据库（MySQL）

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=yoo_buddy
DB_PASSWORD=your_db_password
DB_NAME=yoo_growth_buddy
```

> `config.py` 会根据这些字段组装 `DATABASE_URL`，例如：  
> `mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST:DB_PORT/DB_NAME`

### 大模型（以 DeepSeek 为例）

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

> 如果之后接入 OpenAI / Qwen，可以在 `llm/` 下扩展对应 Provider，  
> 再增加自己的环境变量，例如 `OPENAI_API_KEY`、`QWEN_API_KEY` 等。

### 讯飞语音（ASR + TTS）

```env
XFYUN_APPID=your_xfyun_appid
XFYUN_APIKEY=your_xfyun_apikey
XFYUN_APISECRET=your_xfyun_apisecret
```

### 对象存储（S3 兼容）

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_REGION=auto
AWS_S3_BUCKET=yoo-growth-buddy
AWS_S3_BASE_URL=https://your-cdn-or-endpoint
# 如有自定义 endpoint，可额外加：
# AWS_S3_ENDPOINT_URL=https://your-s3-endpoint
```

- `storage_s3.py` 会基于以上配置初始化 S3 客户端、上传文件，并拼出对外的访问 URL。  
- 对话语音文件的 key 大致形如：  
  `children/{child_id}/sessions/{session_id}/turn_{seq}_user.wav`。

### MQTT

```env
MQTT_BROKER_HOST=127.0.0.1
MQTT_BROKER_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID_PREFIX=yoo-buddy-gw-
```

> 建议使用 Mosquitto 等 Broker，本地调试可以直接 `localhost:1883`。

### 文件存储根目录（本地调试用）

```env
FILE_BASE_PATH=./data
```

> S3 已经是主存储，这个目录主要用于本地调试 / 备选落地。

### 认证（如果后面给家长加登录）

```env
AUTH_JWT_SECRET=change_me_to_a_random_secret
```

> 当前版本如果还没启用家长登录，可以先留这个字段，方便后续扩展。

---

## 运行流程

以下步骤假设你已经安装好 Python 3.10+ 且处于项目根目录。

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. 配置 `.env`

按上一节说明，准备 `.env.example` 并复制为 `.env`，至少要保证：

- 数据库可连通；
- MQTT Broker 地址正确；
- DeepSeek / 讯飞 / S3 的 key 不为空（如果暂时不用某个外部服务，可在代码中选择 dummy provider 或注释对应调用）。

### 3. 初始化数据库

```bash
python init_db.py
```

如果需要测试数据（家长 / 孩子 / 设备绑定等），执行：

```bash
python init_data.py
```

### 4. 启动 FastAPI HTTP 服务

```bash
uvicorn app.main:app --reload --port 8000
```

主要接口：

- `POST /api/parents/setup` – 家长初始化绑定孩子和设备
- `GET  /api/history/children/{child_id}/sessions` – 会话列表
- `GET  /api/history/sessions/{session_id}/turns` – 单次会话详情

Swagger UI：  
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

准备一段 **16kHz 单声道 16bit WAV** 文件（比如：`toy/request/test_input_1.wav`），然后执行：

```bash
python client.py   --host 127.0.0.1   --port 1883   --device-sn abc1244   --input-wav ./toy/request/test_input_1.wav   --output-dir ./toy/reply
```

- `device-sn` 需要和数据库中初始化绑定的设备序列号一致；
- 成功后，会在 `output-dir` 中生成形如 `reply_abc1244_XXXXXXXXXX.wav` 的回复音频文件。

---

## 安全策略 & 可扩展方向

- 所有进入大模型前后的文本都会经过 `domain/safety.py` 中的规则检测；
- 对于孩子发出的内容，如果检测到风险，会在 `Turn` 中记录：
  - `risk_flag=1`
  - `risk_source="user"`
  - `risk_reason` 为命中的规则说明；
- 对于模型回复，一旦检测到风险内容，不会原样返回，而是替换为一段安全的引导话术，DB 中仅保存收敛后的版本。

可以在此基础上扩展：

- 多模型路由（按年龄/场景选不同模型）；
- 更细粒度的审核标签（情绪、欺凌等）；
- 家长 Web 控制台；
- IoT 侧重试 / ACK / QoS 优化。

---

## 许可

本项目默认以 MIT 协议开源（可根据需要调整）。

```text
MIT License
```

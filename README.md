# PhotoStyle AI Assistant - 后端服务

基于 FastAPI + LangGraph + 通义千问 + Milvus + RabbitMQ 的智能拍照助手后端服务，提供用户认证、图片分析、RAG 检索增强、异步反馈入库和个性化拍照建议生成等功能。

## 前端地址

https://github.com/Demonor-alt/photostyle-front

## 目录

- [项目简介](#项目简介)

- [技术栈](#技术栈)

- [功能特性](#功能特性)

- [环境要求](#环境要求)

- [快速开始](#快速开始)

- [项目结构](#项目结构)

- [关键环境变量](#关键环境变量)

## 项目简介

PhotoStyle AI Assistant 后端服务是一个智能拍照建议生成系统。系统通过集成通义千问视觉模型、LangGraph 多节点流程编排、Milvus 向量数据库和 BGE 中文向量模型，为用户提供个性化的拍照建议，包括姿势、服饰、妆造等。

当用户对历史推荐进行评分或反馈后，后端会通过 RabbitMQ 异步触发向量写入任务，将历史输入、推荐输出、用户评分、文字点评和用户长相分析写入 Milvus，形成用户私有的长期风格记忆。后续生成建议时，RAG 模块可根据当前场景召回相似历史偏好，提升推荐的个性化程度。

## 技术栈

- **Web 框架**: FastAPI 0.115.0

- **ASGI 服务器**: Uvicorn 0.30.6

- **AI 流程编排**: LangGraph 0.2.39

- **大模型集成**:

  - DashScope（通义千问）1.24.0

  - OpenAI SDK 1.61.0

- **RAG / 向量检索**:

  - Milvus / pymilvus 2.4.15

  - sentence-transformers 3.0.1

  - BAAI/bge-base-zh-v1.5（默认中文 embedding 模型）

  - HNSW + COSINE 相似度检索

- **消息队列**:

  - RabbitMQ

  - pika 1.3.2

  - 持久化队列与持久化消息

- **数据库**:

  - SQLAlchemy 2.0.34

  - PyMySQL 1.1.1

  - psycopg2-binary 2.9.10

  - 支持 PostgreSQL / MySQL

- **安全**:

  - Passlib[bcrypt] 1.7.4

  - Cryptography 43.0.1

- **数据校验**: Pydantic 2.8.2

- **日志与配置**: python-dotenv、结构化日志、日志文件轮转

## 功能特性

### 核心功能

- **智能建议生成**

  - RAG 检索增强生成

  - 基于 LangGraph 的多 Agent 协作

  - 支持结合历史偏好生成个性化拍照建议

- **历史记录与反馈**

  - 推荐历史保存

  - 用户评分与反馈收集

  - 历史记录查询

  - 反馈更新后异步写入用户私有向量记忆

### 技术特性

- LangSmith 链路追踪支持

- Milvus collection 自动创建与向量维度校验

- RabbitMQ 消息持久化与手动 ack / nack

- 向量写入幂等处理：同一用户同一历史记录先删除旧向量，再插入新向量

## 环境要求

- Python 3.10+

- PostgreSQL 12+ 或 MySQL 5.7+

- RabbitMQ 3.13+（推荐启用 management 插件）

- Milvus 2.4+

- 可访问 HuggingFace 模型或已准备本地 embedding 模型

## 快速开始

### 1. 安装依赖

```bash

pip install -r requirements.txt

```

### 2. 配置环境变量,初始化数据库

### 3. 启动基础设施

#### 启动 RabbitMQ

```bash

docker run -d \

  --name photostyle-rabbitmq \

  --hostname photostyle-rabbitmq \

  --restart unless-stopped \

  -p 5672:5672 \

  -p 15672:15672 \

  -v /data/docker/rabbitmq/data:/var/lib/rabbitmq \

  -v /data/docker/rabbitmq/log:/var/log/rabbitmq \

  -e RABBITMQ_DEFAULT_USER=photostyle \

  -e RABBITMQ_DEFAULT_PASS='123456' \

  rabbitmq:3.13-management

```

#### 启动 Milvus Standalone

```bash

docker network create photo

```

```bash

docker run -d \

  --name milvus-etcd \

  --network photo \

  --restart unless-stopped \

  -p 2379:2379 \

  -v /data/docker/milvus/etcd:/etcd \

  -e ETCD_AUTO_COMPACTION_MODE=revision \

  -e ETCD_AUTO_COMPACTION_RETENTION=1000 \

  -e ETCD_QUOTA_BACKEND_BYTES=4294967296 \

  quay.io/coreos/etcd:v3.5.5 \

  etcd \

  -advertise-client-urls=http://127.0.0.1:2379 \

  -listen-client-urls=http://0.0.0.0:2379 \

  --data-dir=/etcd

```

```bash

docker run -d \

  --name milvus-minio \

  --network photo \

  --restart unless-stopped \

  -p 9000:9000 \

  -p 9001:9001 \

  -v /data/docker/milvus/minio:/minio_data \

  -e MINIO_ACCESS_KEY=minioadmin \

  -e MINIO_SECRET_KEY=minioadmin \

  minio/minio:RELEASE.2023-03-20T20-16-18Z \

  minio server /minio_data --console-address ":9001"

```

```bash

docker run -d \

  --name milvus-standalone \

  --network photo \

  --restart unless-stopped \

  -p 19530:19530 \

  -p 9091:9091 \

  -e ETCD_ENDPOINTS=milvus-etcd:2379 \

  -e MINIO_ADDRESS=milvus-minio:9000 \

  -v /data/docker/milvus/data:/var/lib/milvus \

  milvusdb/milvus:v2.4.6 \

  milvus run standalone

```

可选：启动 Attu 管理界面。

```bash

docker run -d \

  --name attu \

  --restart unless-stopped \

  --network photo \

  -p 3000:3000 \

  zilliz/attu:v2.4.12

```

### 5. 启动服务

启动 API 服务：

```bash

python app/main.py

```

启动反馈 worker：

```bash

python -m app.rabbitmq.feedback_worker

```

## 项目结构

```text
back/
├── app/
│   ├── agents/                    # AI Agent 模块
│   │   ├── base_agent.py
│   │   ├── critic_agent.py
│   │   ├── evaluation_agent.py
│   │   ├── fusion_agent.py
│   │   ├── generator_agent.py
│   │   ├── memory_agent.py
│   │   ├── planner_agent.py
│   │   └── search_agent.py
│   ├── api/                       # API 路由
│   │   ├── history_controller.py
│   │   ├── user_controller.py
│   │   └── utils.py
│   ├── config/                    # 全局配置
│   │   ├── constants.py
│   │   └── enums/
│   ├── db/                        # 数据库层
│   │   ├── database.py
│   │   ├── history_mapper.py
│   │   ├── user_mapper.py
│   │   ├── user_persona_mapper.py
│   │   └── models/
│   │       ├── history_model.py
│   │       ├── user_model.py
│   │       └── user_persona_model.py
│   ├── graph/                     # LangGraph 流程编排
│   │   ├── state.py
│   │   └── workflow.py
│   ├── rabbitmq/                  # RabbitMQ 异步任务
│   │   ├── feedback_rag_consumer.py
│   │   ├── feedback_tasks.py
│   │   ├── feedback_user_profile_consumer.py
│   │   └── feedback_worker.py
│   ├── rag/                       # RAG 检索与向量记忆模块
│   │   ├── embedding/
│   │   ├── milvus_client.py
│   │   ├── semantic_anchor_milvus_service.py
│   │   ├── vector_search.py
│   │   └── vector_writing.py
│   ├── schemas/                   # DTO / ORM / VO / LLM 入参出参
│   │   ├── dto/
│   │   ├── error.py
│   │   ├── llm.py
│   │   ├── orm/
│   │   └── vo/
│   ├── services/                  # 业务服务
│   │   ├── llm/
│   │   │   ├── qwen_client.py
│   │   │   ├── qwen_face_client.py
│   │   │   ├── qwen_suggest_client.py
│   │   │   └── qwen_user_persona_analysis_client.py
│   │   ├── orchestrator.py
│   │   └── user_persona_service.py
│   ├── utils/                     # 工具模块
│   │   ├── runtime.py
│   │   ├── semantic_anchors.py
│   │   └── to_json.py
│   └── main.py                    # FastAPI 应用入口
├── logs/                          # 日志目录
├── uploads/                       # 上传文件目录
├── migrate_to_orm.py              # 数据库迁移脚本
├── .env.example                   # 环境变量示例
├── requirements.txt               # Python 依赖
└── README.md                      # 本文件
```

## 关键环境变量

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 无 | 通义千问 DashScope API Key |
| `DATABASE_URL` | 无 | 数据库连接地址 |
| `MILVUS_URI` | `http://localhost:19530` | Milvus 连接地址 |
| `MILVUS_TOKEN` | 空 | Milvus 认证 token，本地无认证可不填 |
| `MILVUS_COLLECTION_NAME` | `photo_style_embeddings` | RAG 使用的 collection 名称 |
| `MILVUS_ALIAS` | `default` | pymilvus 连接别名 |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-base-zh-v1.5` | sentence-transformers 模型名或本地模型路径 |
| `EMBEDDING_DEVICE` | 自动选择 | embedding 运行设备，如 `cpu`、`cuda`、`cuda:0` |
| `BGE_QUERY_PREFIX` | `为这个句子生成表示以用于检索相关文章：` | BGE 查询侧前缀，可置空 |
| `RABBITMQ_URL` | 无 | RabbitMQ AMQP 连接地址 |
| `RABBITMQ_REVIEW_SUBMITTED_EXCHANGE` | 无 | 点评提交事件交换机名 |
| `RABBITMQ_REVIEW_SUBMITTED_ROUTING_KEY` | 无 | 点评提交事件路由键 |
| `RABBITMQ_FEEDBACK_RAG_QUEUE` | 无 | RAG 向量写入队列名 |
| `RABBITMQ_FEEDBACK_USER_PROFILE_QUEUE` | 无 | 用户画像更新队列名 |
| `RABBITMQ_HEARTBEAT` | `600` | RabbitMQ 心跳间隔，适配较长耗时的向量写入 |
| `RABBITMQ_BLOCKED_TIMEOUT` | `300` | RabbitMQ 阻塞连接超时时间 |
| `DEBUG` | `false` | 是否启用调试输出 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_KEEP_DAYS` | `3` | 日志文件保留天数 |
| `LOG_MAX_BYTES` | `10485760` | 单个日志文件最大大小 |

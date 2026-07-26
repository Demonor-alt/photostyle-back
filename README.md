# PhotoStyle AI Assistant - 后端服务

基于 FastAPI + LangGraph + 通义千问的智能拍照助手后端服务，提供用户认证、图片分析、RAG 检索和智能建议生成等功能。

## 前端地址
https://github.com/Demonor-alt/photostyle-front

## 📋 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [API 文档](#api-文档)


## 项目简介

PhotoStyle AI Assistant 后端服务是一个智能拍照建议生成系统，通过集成通义千问视觉模型和 RAG 检索增强，为用户提供个性化的拍照建议，包括姿势、构图、光线、拍摄参数等全方位指导。

## 技术栈

- **Web 框架**: FastAPI 0.115.0
- **ASGI 服务器**: Uvicorn 0.30.6
- **AI 框架**: LangGraph 0.2.39
- **大模型集成**: 
  - DashScope (通义千问) 1.24.0
  - OpenAI SDK 1.61.0
- **数据库**: 
  - SQLAlchemy 2.0.34 (ORM)
  - PyMySQL 1.1.1 (MySQL 驱动)
  - psycopg2-binary 2.9.10 (PostgreSQL 驱动)
  - 支持 PostgreSQL / MySQL
- **安全**: 
  - Passlib[bcrypt] 1.7.4
  - Cryptography 43.0.1
- **数据校验**: Pydantic 2.8.2

## 功能特性

### 核心功能

- ✅ **用户认证系统**
  - 用户注册/登录
  - 密码加密存储 (bcrypt)
  - 用户资料管理

- ✅ **图片分析**
  - 基于通义千问视觉模型的人脸检测
  - 人脸特征分析
  - 图片本地存储管理

- ✅ **智能建议生成**
  - RAG 检索增强生成
  - 基于 LangGraph 的多 Agent 协作
  - 支持流式输出 (SSE)
  - 个性化拍照建议

- ✅ **历史记录**
  - 推荐历史保存
  - 用户反馈收集
  - 历史记录查询

### 技术特性

- 🔥 异步 API 设计
- 🔥 统一错误处理
- 🔥 CORS 跨域支持
- 🔥 结构化日志
- 🔥 LangSmith 链路追踪
- 🔥 数据库连接池

## 环境要求

- Python 3.10+
- PostgreSQL 12+ 或 MySQL 5.7+

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
# 通义千问 API Key（必填）
DASHSCOPE_API_KEY=your_qwen_dashscope_api_key

# 数据库配置（二选一）
# PostgreSQL (推荐)
DATABASE_URL=postgresql://user:password@localhost:5432/photostyle

# MySQL
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/photostyle
```

### 3. 初始化数据库

#### PostgreSQL

```bash
# 创建数据库
createdb photostyle
```

#### MySQL

```sql
CREATE DATABASE photostyle CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. 启动服务

```bash
# 开发模式
python app/main.py
python -m app.rabbitmq.feedback_worker
docker run -d   --name photostyle-rabbitmq   --hostname photostyle-rabbitmq   --restart unless-stopped   -p 5672:5672   -p 15672:15672   -v /data/docker/rabbitmq/data:/var/lib/rabbitmq   -v /data/docker/rabbitmq/log:/var/log/rabbitmq   -e RABBITMQ_DEFAULT_USER=photostyle   -e RABBITMQ_DEFAULT_PASS='123456'   rabbitmq:3.13-management
docker run -d \
  --name milvus-standalone \
  --restart unless-stopped \
  --network photo \
  -p 19530:19530 \
  -p 9091:9091 \
  -v /data/docker/milvus/data:/var/lib/milvus \
  -v /data/docker/milvus/log:/var/log/milvus \
  -v /data/docker/milvus/conf:/milvus/configs \
  milvusdb/milvus:v2.4.6 \
  milvus run standalone
docker run -d \
  --name attu \
  --restart unless-stopped \
  --network photo \
  -p 3000:3000 \
  zilliz/attu:v2.4.12
```

服务启动后访问：

- API 根路径: http://localhost:8000
- API 文档 (Swagger): http://localhost:8000/docs
- API 文档 (ReDoc): http://localhost:8000/redoc

## 项目结构

```
back/
├── app/
│   ├── agents/              # AI Agent 模块
│   │   ├── evaluation_agent.py    # 评估 Agent
│   │   └── rag_agent.py          # RAG 检索 Agent
│   ├── api/                 # API 路由
│   ├── db/                  # 数据库层
│   │   ├── database.py           # 数据库连接和会话
│   │   ├── user_service.py       # 用户服务
│   │   └── history_service.py    # 历史服务
│   ├── models/              # ORM 模型
│   │   ├── user.py               # 用户模型
│   │   └── history.py            # 历史记录模型
│   ├── graph/               # LangGraph 流程编排
│   ├── rag/                 # RAG 检索模块
│   ├── services/            # 业务服务
│   ├── utils/               # 工具模块
│   └── main.py              # FastAPI 应用入口
├── logs/                    # 日志目录
├── uploads/                 # 上传文件目录
├── migrate_to_orm.py        # 数据库迁移脚本
├── .env.example             # 环境变量示例
├── requirements.txt         # Python 依赖
└── README.md               # 本文件
```

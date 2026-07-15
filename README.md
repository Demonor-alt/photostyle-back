# PhotoStyle AI Assistant - 后端服务

基于 FastAPI + LangGraph + 通义千问的智能拍照助手后端服务，提供用户认证、图片分析、RAG 检索和智能建议生成等功能。

## 📋 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [API 文档](#api-文档)
- [配置说明](#配置说明)
- [开发指南](#开发指南)

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
  - SQLAlchemy 2.0.34
  - PyMySQL 1.1.1
  - MySQL
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
  - 人脸特征分析（年龄、性别、表情等）
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
- MySQL 5.7+ / 8.0+
- 通义千问 API Key

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd back
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 通义千问 API Key（必填）
DASHSCOPE_API_KEY=your_qwen_dashscope_api_key

# MySQL 数据库配置
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=photostyle
MYSQL_POOL_ENABLED=false

# 可选：LangSmith 链路追踪
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=your_langsmith_api_key
# LANGCHAIN_PROJECT=photostyle

# 可选：调试模式
# DEBUG=true
```

### 5. 初始化数据库

创建 MySQL 数据库：

```sql
CREATE DATABASE photostyle CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

启动服务后会自动创建表结构。

### 6. 启动服务

```bash
# 开发模式（自动重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
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
│   │   ├── rag_agent.py          # RAG 检索 Agent
│   │   └── __init__.py
│   ├── api/                 # API 路由
│   │   ├── routes.py             # 路由定义
│   │   └── __init__.py
│   ├── db/                  # 数据库层
│   │   ├── connection.py         # 数据库连接
│   │   ├── schema.py             # 表结构定义
│   │   ├── mysql_repo.py         # 数据仓库
│   │   ├── user_service.py       # 用户服务
│   │   ├── history_service.py    # 历史服务
│   │   └── __init__.py
│   ├── graph/               # LangGraph 流程编排
│   ├── rag/                 # RAG 检索模块
│   ├── services/            # 业务服务
│   │   ├── orchestrator.py       # 流程调度器
│   │   └── qwen_face_client.py   # 通义千问客户端
│   ├── utils/               # 工具模块
│   │   └── runtime.py            # 运行时配置
│   ├── main.py              # FastAPI 应用入口
│   └── models.py            # Pydantic 数据模型
├── logs/                    # 日志目录
├── uploads/                 # 上传文件目录
├── .env.example             # 环境变量示例
├── requirements.txt         # Python 依赖
└── README.md               # 本文件
```

## API 文档

### 认证相关

#### 注册用户
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "user123",
  "password": "password123"
}
```

#### 用户登录
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "user123",
  "password": "password123"
}
```

#### 获取当前用户信息
```http
GET /api/auth/me?username=user123
```

### 照片管理

#### 上传照片
```http
POST /api/photos/upload
Content-Type: multipart/form-data

username: user123
image: <file>
```

#### 预览照片
```http
GET /api/photos/preview?path=/path/to/image.jpg
```

### 建议生成

#### 生成拍照建议（同步）
```http
POST /api/suggest
Content-Type: multipart/form-data

username: user123
style: 街拍
location: 城市街道
time: 傍晚
weather: 晴天
face_tags: ["瓜子脸", "丹凤眼"]
shot_tags: ["半身照"]
pose_tags: ["自然站姿"]
extra_tags: []
image: <file> (可选)
```

#### 生成拍照建议（流式 SSE）
```http
POST /api/suggest/stream
Content-Type: multipart/form-data

(参数同上)
```

SSE 事件格式：
```
event: status
data: {"message": "started"}

event: chunk
data: {"step": "rag", "result": {...}}

event: done
data: {"message": "completed"}
```

### 历史记录

#### 保存历史记录
```http
POST /api/history
Content-Type: application/json

{
  "input_data": {...},
  "output_data": {...},
  "liked": false,
  "shot_success": false
}
```

#### 查询历史记录
```http
GET /api/history
```

### 反馈

#### 提交用户反馈
```http
POST /api/feedback
Content-Type: application/json

{
  "liked": true,
  "shot_success": true,
  "input_data": {...},
  "output_data": {...}
}
```

### 系统状态

#### 数据库状态检查
```http
GET /api/db/status
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 必填 | 默认值 |
|--------|------|------|--------|
| `DASHSCOPE_API_KEY` | 通义千问 API Key | 是 | - |
| `MYSQL_HOST` | MySQL 主机地址 | 是 | 127.0.0.1 |
| `MYSQL_PORT` | MySQL 端口 | 是 | 3306 |
| `MYSQL_USER` | MySQL 用户名 | 是 | root |
| `MYSQL_PASSWORD` | MySQL 密码 | 是 | - |
| `MYSQL_DATABASE` | 数据库名称 | 是 | photostyle |
| `MYSQL_POOL_ENABLED` | 启用连接池 | 否 | false |
| `DEBUG` | 调试模式 | 否 | false |
| `LANGCHAIN_TRACING_V2` | LangSmith 追踪 | 否 | false |
| `LANGCHAIN_API_KEY` | LangSmith API Key | 否 | - |
| `LANGCHAIN_PROJECT` | LangSmith 项目名 | 否 | photostyle |

### 日志配置

日志文件保存在 `logs/app.log`，支持自动轮转。

日志配置可通过环境变量调整：
- `LOG_LEVEL`: 日志级别（DEBUG/INFO/WARNING/ERROR）
- `LOG_MAX_BYTES`: 单文件最大字节数
- `LOG_KEEP_DAYS`: 日志保留天数

## 开发指南

### 添加新的 API 接口

1. 在 `app/models.py` 中定义请求/响应模型
2. 在 `app/api/routes.py` 中添加路由处理函数
3. 根据需要在 `app/services/` 中添加业务逻辑
4. 更新 API 文档

### 自定义 Agent

1. 在 `app/agents/` 目录创建新的 Agent 文件
2. 实现 Agent 逻辑
3. 在 `app/graph/` 中将 Agent 集成到 LangGraph 流程
4. 在 `app/services/orchestrator.py` 中调用

### 数据库迁移

目前使用 SQLAlchemy 自动创建表，生产环境建议使用 Alembic 进行版本管理。

### 测试

```bash
# 运行单元测试（需要添加测试文件）
pytest

# 代码格式化
black app/

# 类型检查
mypy app/
```

### 常见问题

**Q: 启动时报 "数据库连接失败"**
A: 检查 MySQL 服务是否启动，`.env` 配置是否正确，数据库是否已创建。

**Q: 图片上传后提示 "未检测到人脸"**
A: 确保上传的图片清晰且包含正面人脸，检查 DASHSCOPE_API_KEY 是否有效。

**Q: 流式接口没有输出**
A: 检查前端是否正确处理 SSE，查看后端日志是否有异常。

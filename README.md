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
- MySQL 5.7+ / 8.0+

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```
# 通义千问 API Key（必填）
DASHSCOPE_API_KEY=your_qwen_dashscope_api_key

# MySQL 数据库配置
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=photostyle
```

### 3. 初始化数据库

创建 MySQL 数据库：

```sql
CREATE DATABASE photostyle CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

启动服务后会自动创建表结构。

### 4. 启动服务

```bash
# 开发模式（自动重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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
│   ├── api/                 # API 路由
│   │   ├── routes.py             # 路由定义
│   ├── db/                  # 数据库层
│   │   ├── connection.py         # 数据库连接
│   │   ├── schema.py             # 表结构定义
│   │   ├── mysql_repo.py         # 数据仓库
│   │   ├── user_service.py       # 用户服务
│   │   ├── history_service.py    # 历史服务
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
# RAG 向量记忆机制与RabbitMQ 反馈任务机制

## 目录

- [RAG 向量记忆机制](#rag-向量记忆机制)

- [RabbitMQ 反馈任务机制](#rabbitmq-反馈任务机制)

## RAG 向量记忆机制

RAG 相关代码位于 `app/rag/`，主要包含：

```text

app/rag/

├── embedding/

│   ├── __init__.py          # 统一导出 embedding 能力

│   └── bge_client.py        # BGE 中文向量模型客户端

├── vector_search.py         # Milvus 向量检索服务

└── vector_writing.py        # Milvus 向量写入与文本构建服务

```

### 1. Embedding 模型

默认使用 `BAAI/bge-base-zh-v1.5` 作为中文向量模型，可通过环境变量 `EMBEDDING_MODEL_NAME` 指定 HuggingFace 模型名或本地模型目录。

- 文档入库：直接对历史文本向量化。

- 查询检索：默认添加 BGE 查询前缀 `为这个句子生成表示以用于检索相关文章：`，提升检索语义匹配效果。

- 向量归一化：使用 `normalize_embeddings=True`。

- 设备选择：可通过 `EMBEDDING_DEVICE` 指定 `cpu`、`cuda`、`cuda:0` 等。

### 2. 向量写入

`vector_writing.py` 会将一条历史记录转换为统一的 Milvus 写入载荷。入库文本包含：

- 当前拍摄需求：风格、时间、地点、天气、额外标签

- 完整输入数据快照

- 完整输出推荐结果快照

- 用户平均评分

- 用户文字点评

- 用户长相分析摘要，例如脸型、线条感、五官量感、肤色、肤质、气质、风格向量等

写入流程：

1. 连接 Milvus。

2. 检查 collection 是否存在。

3. 如果不存在，则自动创建 collection 和索引。

4. 如果已存在，则校验 collection 的向量维度是否与当前 embedding 模型一致。

5. 根据 `history_id` 查询历史记录，根据 `user_id` 查询用户资料。

6. 构建文本并生成 embedding。

7. 删除同一 `history_id` + `user_id` + `doc_type` 的旧向量。

8. 插入新向量并 flush。

默认 collection：`photo_style_embeddings`。

字段设计：

| 字段 | 类型 | 说明 |

| --- | --- | --- |

| `id` | INT64 auto_id | Milvus 主键 |

| `history_id` | INT64 | 历史记录 ID |

| `user_id` | INT64 | 用户 ID，用于用户数据隔离 |

| `doc_type` | VARCHAR | 文档类型，当前默认为 `history_feedback` |

| `embedding` | FLOAT_VECTOR | 文本向量 |

| `metadata` | JSON | 完整业务元数据和调试信息 |

索引设计：

- `embedding`: HNSW，`metric_type=COSINE`，`M=16`，`efConstruction=200`

- `history_id`: 标量索引

- `user_id`: 标量索引

### 3. 向量检索

`vector_search.py` 提供 `search_photo_style_memories`，用于检索与当前 query 最相关的用户历史记忆。

检索特点：

- 强制按 `user_id` 过滤，避免召回其他用户的私有记忆。

- 默认只召回 `doc_type == 'history_feedback'` 的历史反馈记忆。

- 支持 `top_k` 控制返回数量。

- 支持 `min_score` 过滤低相关结果。

- 支持业务过滤条件：

  - `min_avg_score`

  - `history_id`

  - `only_positive`

  - `style`

  - `weather`

  - `location`

  - `doc_type`

示例调用：

```python

from app.rag.vector_search import search_photo_style_memories



memories = search_photo_style_memories(

    user_id=1,

    query_text="海边日落氛围感写真，想要自然高级的姿势和构图",

    top_k=5,

    min_score=0.3,

    filters={

        "only_positive": True,

        "style": "氛围感",

    },

)

```

## RabbitMQ 反馈任务机制

RabbitMQ 相关代码位于 `app/rabbitmq/`：

```text

app/rabbitmq/

├── feedback_tasks.py      # 反馈消息发布、消费和处理逻辑

└── feedback_worker.py     # worker 启动入口

```

### 1. 设计目的

用户提交反馈后，向量化和 Milvus 写入可能较耗时。如果直接在 API 请求中同步执行，会增加接口响应时间。因此系统使用 RabbitMQ 将“反馈更新后写入向量记忆”的任务异步化。

### 2. 消息发布

`publish_feedback_updated(history_id)` 会发布一条 JSON 消息到反馈队列：

```json

{

  "history_id": 123,

  "event": "feedback.updated",

  "created_at": 1720000000

}

```

消息特性：

- 使用默认交换机。

- routing key 为 `RABBITMQ_FEEDBACK_QUEUE`。

- 队列声明为 durable。

- 消息设置为 persistent。

- content type 为 `application/json`。

### 3. 消息消费

`consume_feedback_tasks()` 会持续监听反馈队列：

1. 建立 RabbitMQ 连接。

2. 声明持久化反馈队列。

3. 设置 `prefetch_count=1`，每次只处理一条任务。

4. 解析消息中的 `history_id`。

5. 查询历史记录和用户资料。

6. 调用 `upsert_photo_style_embedding(history_id, user_id)` 写入或更新 Milvus 向量。

7. 成功后手动 `ack`。

8. 业务异常时 `nack(requeue=False)`，避免异常消息无限重试。

worker 启动命令：

```bash

python -m app.rabbitmq.feedback_worker

```

> 注意：API 服务和 RabbitMQ worker 是两个独立进程。生产环境中需要同时运行 API 服务、RabbitMQ、Milvus 及 worker。

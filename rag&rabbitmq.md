# 用户评论反馈机制

## 目录

- [整体数据流](#整体数据流)
- [用户画像模块](#用户画像模块)
- [RAG 向量记忆机制](#rag-向量记忆机制)
- [RabbitMQ 反馈任务机制](#rabbitmq-反馈任务机制)

## 整体数据流

```text
用户生成推荐建议DC，history 表保存 input_data / output_data / 评分 / feedback_comment
        ↓
用户提交点评
        ↓
API 发布 ReviewSubmitted 事件到 RabbitMQ fanout 交换机
        ├── 用户画像队列：语义锚点检索 + LLM 分析 + 画像融合更新
        └── RAG 队列：读取历史与用户资料 + 更新 Milvus 历史记忆向量
        ↓
后续推荐使用当前场景 query 检索当前用户的历史记忆
```

用户画像更新与 RAG 写入是两个相互独立的消费者。二者都消费同一个 `ReviewSubmitted` 事件，因此画像更新失败不会阻塞 RAG 写入，RAG 写入失败也不会阻塞画像更新。

## 用户画像模块

用户画像数据模型位于 `app/db/models/user_persona_model.py`，每个用户对应一条 `user_persona` 记录：

| 字段 | 说明 |
| --- | --- |
| `user_id` | 用户 ID，唯一关联用户 |
| `semantic_axes` | 用户语义偏好轴 JSON |
| `created_at` / `updated_at` | 画像创建和更新时间 |

当前默认语义轴在scripts/semantic_axes.yaml

### 画像更新流程

用户提交点评后

1. 根据 `history_id` 读取当前历史记录。
2. 使用 `feedback_comment` 检索全局 Semantic Anchor Library。
3. 按语义轴聚合相似锚点，仅保留达到相似度阈值且证据数量足够的候选。
4. 将当前输入、推荐输出、点评、评分、旧画像和语义锚点候选发送给 Qwen 用户偏好分析客户端。
5. 根据 `semantic_axes.yaml` 的 `effect_field`，使用对应的妆容、穿搭、姿势评分计算本次更新权重。
6. 融合旧画像、LLM 分析结果和 Milvus 语义锚点结果，得到最终语义轴值。
7. 通过 `update_user_persona_by_id` 更新或创建用户画像。

画像融合的核心约束如下：

- 用户历史越多，旧画像权重越高，避免单次点评造成画像剧烈漂移。
- 评分越高，对应评分字段影响的语义轴本次更新权重越大。
- 语义锚点只提供有限的辅助权重，不能覆盖稳定的历史画像。
- 最终语义轴值会限制在合法范围内。

用户画像本身不直接写入照片风格历史向量；它通过 RAG 文本中的用户特征和独立的画像更新流程共同参与后续推荐。

## RAG 向量记忆机制

RAG 相关代码位于 `app/rag/`：

```text
app/rag/
├── embedding/                       # BGE embedding 客户端
├── semantic_anchor_milvus_service.py # Semantic Anchor Library 检索
├── vector_search.py                  # 照片风格历史记忆检索
└── vector_writing.py                 # 历史记忆文本构建与 Milvus 写入
```

### 1. Embedding 模型

默认使用 `BAAI/bge-base-zh-v1.5`，可通过 `EMBEDDING_MODEL_NAME` 指定 HuggingFace 模型名或本地目录。

- 文档入库使用原始文本向量。
- 向量使用 `normalize_embeddings=True` 归一化。
- 可通过 `EMBEDDING_DEVICE` 指定 `cpu`、`cuda` 或 `cuda:0`。

### 2. 向量写入内容

`build_photo_style_embedding_payload` 将一条历史记录和用户资料转换为统一载荷。Embedding 文本包含：

- 当前拍摄需求：风格、时间、地点、天气、额外标签。
- 完整 `input_data` 快照。
- 完整 `output_data` 推荐结果快照。
- 妆容、穿搭、姿势平均评分。
- 用户文字点评。
- 用户长相分析 `face_analysis.simple_analysis`，包括脸型、线条感、五官量感、肤色、肤质、气质、五官细节和风格向量。

当前实现将用户长相分析压平为文本参与向量化，示例：

```text
用户长相:脸型:...；线条感:...；肤色:...；气质:...；风格向量:...
```

需要注意：当前 RAG 历史记忆的 metadata 保存的是 `simple_analysis` 和历史场景信息，`semantic_axes` 保存在独立的 `user_persona` 表中，不作为历史向量文档的独立字段写入。

### 3. Milvus collection 与字段

默认 collection 名称由 `MILVUS_COLLECTION_NAME` 配置。写入时会检查 collection 是否存在；不存在则按当前 embedding 维度创建，已存在则校验向量维度是否一致。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `INT64 auto_id` | Milvus 主键 |
| `history_id` | `INT64` | 历史记录 ID |
| `user_id` | `INT64` | 用户隔离字段 |
| `doc_type` | `VARCHAR` | 当前为 `history_feedback` |
| `embedding` | `FLOAT_VECTOR` | 历史记忆文本向量 |
| `metadata` | `JSON` | 场景、评分、点评、用户长相和快照 |

metadata 主要包含：`history_id`、`doc_type`、`time`、`style`、`weather`、`location`、`tags`、`avg_score`、`is_positive_feedback`、`created_at`、`updated_at`、`input_data`、`output_data`、`feedback_comment`、`simple_analysis`、`source` 和 `embedding_model`。

索引配置：

- `embedding`：HNSW，`metric_type=COSINE`，`M=16`，`efConstruction=200`。
- `history_id`：标量索引。
- `user_id`：标量索引。

每次写入前会删除同一 `history_id + user_id + doc_type` 的旧记录，再插入新向量，保证 RabbitMQ 重复投递不会产生重复记忆。

### 4. 向量检索

`search_photo_style_memories` 强制按 `user_id` 过滤，默认只检索 `history_feedback`，并支持：

- `top_k`：返回数量。
- `min_score`：最低余弦相似度。
- `min_avg_score`：最低平均评分。
- `history_id`：指定历史记录。
- `only_positive`：只召回正向或负向反馈。
- `style`、`weather`、`location`、`doc_type`：业务过滤条件。

## RabbitMQ 反馈任务机制

RabbitMQ 相关代码位于 `app/rabbitmq/`：

```text
app/rabbitmq/
├── feedback_tasks.py                   # 连接、事件发布、交换机和队列声明
├── feedback_rag_consumer.py            # RAG 向量写入消费者
├── feedback_user_profile_consumer.py   # 用户画像更新消费者
└── feedback_worker.py                  # 同时启动两个消费者
```

### 1. 事件发布

用户提交点评后，调用 `publish_review_submitted(history_id)` 发布事件。旧函数名 `publish_feedback_updated` 仍保留，并委托给新事件发布函数。

事件消息：

```json
{
  "history_id": 123,
  "event": "ReviewSubmitted",
  "created_at": 1720000000
}
```

消息发布到持久化 `fanout` 交换机 `RABBITMQ_REVIEW_SUBMITTED_EXCHANGE`，路由键为 `RABBITMQ_REVIEW_SUBMITTED_ROUTING_KEY`。消息使用 persistent delivery mode，类型为 `ReviewSubmitted`，内容类型为 `application/json`。

### 2. 两个消费者

`feedback_worker.py` 在同一进程中启动两个非守护线程：

- **RAG Consumer**：从 `RABBITMQ_FEEDBACK_RAG_QUEUE` 消费事件，读取历史记录中的 `user_id`，调用 `upsert_photo_style_embedding` 写入或更新 Milvus。
- **UserProfile Consumer**：从 `RABBITMQ_FEEDBACK_USER_PROFILE_QUEUE` 消费事件，调用 `user_persona_semantic_axes`，完成语义锚点检索、Qwen 分析和用户画像更新。

两个队列都绑定到同一个 `ReviewSubmitted` fanout 交换机，因此一条点评事件会分别投递给两个业务消费者。

### 3. 可靠性与失败处理

- 两个消费者均使用 `prefetch_count=1`，避免单个 worker 预取过多任务。
- 业务处理成功后手动 `basic_ack`。
- 业务异常使用 `basic_nack(requeue=False)`，消息进入该队列配置的死信交换机和死信队列，避免无限重试。
- RabbitMQ 连接异常按 AMQP 异常抛出，由进程层感知。
- 每个业务队列都有独立的 `.dlx` 和 `.dlq`，便于隔离和排查失败消息。
- RAG 写入具备删除旧向量再插入新向量的幂等处理。

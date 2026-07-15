# 企业级智能客服系统（RAG + Agent）

本项目是一个可生产化扩展的智能客服参考实现，使用 **Python + FastAPI + LangChain/LangGraph + PostgreSQL/pgvector + Redis + Qwen/DeepSeek OpenAI-compatible API** 构建。系统支持知识库问答、多轮会话、订单/工单等业务工具调用、人工转接和 Docker 一键部署。

## 架构概览

```text
Client/Web/IM
   │
   ▼
FastAPI API Gateway
   │  /chat /knowledge/ingest /health
   ▼
LangGraph Agent Workflow
   ├─ Intent Classifier：订单、退款、人工、通用问题
   ├─ RAG Retriever：PostgreSQL + pgvector 知识库检索
   ├─ Business Tools：订单查询、人工工单创建
   └─ Answer Generator：Qwen/DeepSeek/OpenAI-compatible Chat Model
   │
   ├─ PostgreSQL：客户、订单、工单、知识向量
   └─ Redis：多轮会话记忆与缓存基础设施
```

## 项目结构

```text
customer_service_agent/
  api.py              # FastAPI 应用与 HTTP DTO
  graph.py            # LangGraph 编排：分类、RAG、工具、转人工、回答生成
  database.py         # SQLAlchemy 业务数据模型与仓储
  vector_store.py     # pgvector 知识库索引与检索
  memory.py           # Redis 多轮对话记忆
  llm.py              # Qwen/DeepSeek/OpenAI-compatible LLM 与 Embedding 工厂
  config.py           # Pydantic Settings 统一配置
  tools.py            # LangChain 工具封装
  knowledge_base.py   # 本地 FAQ 检索兜底，便于测试/离线开发
  cache.py            # 进程内 TTL 缓存

deploy/schema.sql     # PostgreSQL + pgvector 表结构
docker-compose.yml    # API + PostgreSQL/pgvector + Redis
Dockerfile            # 生产镜像构建
```

## 核心能力

- **RAG 知识库问答**：`PgVectorKnowledgeBase` 将企业文档切片后写入 `knowledge_chunks`，通过 `embedding <=> query_vector` 做余弦距离检索。
- **Agent 工作流**：`LangGraph` 按意图路由到知识检索、订单工具或人工转接节点，避免所有问题都走单一提示词。
- **业务工具调用**：订单状态查询、售后状态查询和人工工单创建均通过 SQLAlchemy 仓储隔离实现。
- **多轮对话**：FastAPI 根据 `conversation_id` 从 Redis 加载上下文，并在回答后写回最近窗口。
- **国产模型适配**：默认配置兼容 DashScope/Qwen；替换 `CUSTOMER_SERVICE_LLM_BASE_URL`、`CUSTOMER_SERVICE_LLM_MODEL` 和 API Key 即可使用 DeepSeek 等 OpenAI-compatible 服务。
- **生产部署基础**：Docker Compose 包含 API、PostgreSQL/pgvector、Redis；配置通过 `.env` 注入。

## 数据库设计

| 表 | 用途 |
| --- | --- |
| `customers` | 客户手机号、姓名、会员等级。 |
| `orders` | 订单状态、物流、退款状态，是订单查询工具的数据源。 |
| `service_tickets` | 人工转接工单和对话摘要。 |
| `knowledge_chunks` | 知识库文本切片、元数据和 pgvector 向量。 |

完整 DDL 见 `deploy/schema.sql`。

## 本地开发

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

离线测试可使用规则模型和 SQLite：

```bash
export CUSTOMER_SERVICE_FAKE_LLM=1
python -m customer_service_agent.cli
```

运行测试：

```bash
pytest
```

## Docker 部署

1. 配置环境变量：

```bash
cp .env.example .env
# 编辑 .env，填写 CUSTOMER_SERVICE_LLM_API_KEY / DASHSCOPE_API_KEY 或 DEEPSEEK_API_KEY
```

2. 启动服务：

```bash
docker compose up --build -d
```

3. 健康检查：

```bash
curl http://localhost:8000/health
```

4. 对话接口：

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"我的订单 A1001 到哪了？"}'
```

5. 知识库导入：

```bash
curl -X POST http://localhost:8000/knowledge/ingest \
  -H 'Content-Type: application/json' \
  -d '{"documents":[{"content":"黑金会员享专属客服和优先换货。","source":"policy","title":"会员权益"}]}'
```

## 生产化扩展建议

- **鉴权与租户隔离**：在 FastAPI 增加 JWT/API Key 鉴权，并在业务表和知识库增加 `tenant_id`。
- **异步摄取流水线**：将文档解析、切片、Embedding 写入放到 Celery/RQ/Kafka 消费者中，避免阻塞 API。
- **可观测性**：接入 OpenTelemetry、结构化日志、Prometheus 指标，记录意图、检索命中、工具延迟和模型 token 成本。
- **安全护栏**：增加敏感信息脱敏、提示词注入检测、工具权限白名单和人工审核策略。
- **高可用**：API 水平扩容，Redis 使用托管集群，PostgreSQL 配置备份、只读副本与 pgvector 索引维护计划。

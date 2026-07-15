# LangGraph 智能客服示例

这是一个使用 LangChain + LangGraph 构建的智能客服示例项目，包含：

- 意图识别：区分订单查询、退款政策、人工客服转接和通用咨询。
- RAG 知识库：基于内置 FAQ 文档进行检索增强回答。
- 工具调用：通过 MySQL 业务数据库查询订单、退款和人工工单数据。
- 状态图编排：用 LangGraph 将分类、工具、RAG、人工转接和回复生成串联起来。
- CLI 交互：可在终端模拟多轮客服对话。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

默认使用 OpenAI Chat Completions 模型，请设置：

```bash
export OPENAI_API_KEY="你的 API Key"
export CUSTOMER_SERVICE_MODEL="gpt-4o-mini"  # 可选，默认 gpt-4o-mini
```

业务数据默认写入本地 SQLite 文件。若要本地启动 MySQL，可运行：

```bash
docker compose up -d mysql
```

生产或联调 MySQL 时请设置 SQLAlchemy DSN：

```bash
export CUSTOMER_SERVICE_DB_URL="mysql+pymysql://user:password@127.0.0.1:3306/customer_service?charset=utf8mb4"
export CUSTOMER_SERVICE_AUTO_INIT_DB=1       # 可选，默认自动建表
export CUSTOMER_SERVICE_SEED_DEMO_DATA=1     # 可选，默认写入演示数据
python -m customer_service_agent.init_db
```

缓存默认启用，用于减少重复订单查询和 FAQ 检索计算；可按需调整：

```bash
export CUSTOMER_SERVICE_CACHE_ENABLED=1
export CUSTOMER_SERVICE_CACHE_TTL_SECONDS=300
export CUSTOMER_SERVICE_CACHE_MAX_SIZE=512
```

如需在无 API Key 环境下体验流程，可启用规则兜底模型：

```bash
export CUSTOMER_SERVICE_FAKE_LLM=1
```

## 运行

```bash
python -m customer_service_agent.cli
```

示例输入：

- `我的订单 A1001 到哪了？`
- `我想申请退款`
- `我要找人工客服`

## 业务数据表

项目使用 SQLAlchemy ORM 管理以下业务表：

- `customers`：客户姓名、手机号、会员等级。
- `orders`：订单状态、商品、物流、退款状态。
- `service_tickets`：人工转接工单和对话摘要。

## 缓存机制

项目提供进程内 TTL 缓存：

- 订单查询：缓存 `BusinessDataStore.get_order()` 的订单快照，降低 MySQL 读压力。
- FAQ 检索：缓存相同问题和 limit 的检索结果，减少重复排序计算。
- 可观测性：`BusinessDataStore.cache_stats()` 可查看命中、未命中和当前条目数。
- 失效策略：演示数据写入后自动清空订单缓存；TTL 到期或超过最大容量时自动淘汰。

## 测试

```bash
pytest
```

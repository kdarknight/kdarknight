CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS customers (
    id BIGSERIAL PRIMARY KEY,
    phone VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(80) NOT NULL,
    membership_level VARCHAR(32) NOT NULL DEFAULT '普通会员',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(32) PRIMARY KEY,
    customer_id BIGINT REFERENCES customers(id),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    item_name VARCHAR(160) NOT NULL,
    logistics_status TEXT NOT NULL,
    refund_status VARCHAR(160),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS service_tickets (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT REFERENCES customers(id),
    channel VARCHAR(32) NOT NULL DEFAULT 'chat',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    subject VARCHAR(160) NOT NULL,
    transcript TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(256) NOT NULL,
    title VARCHAR(256) NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    chunk_metadata JSONB NOT NULL DEFAULT '{}',
    embedding vector(1024) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source ON knowledge_chunks(source);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

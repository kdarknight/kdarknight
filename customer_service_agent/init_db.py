"""Initialize the business database for the customer service agent."""

from __future__ import annotations

from .database import BusinessDataStore


def main() -> None:
    store = BusinessDataStore()
    store.create_schema()
    store.seed_demo_data()
    print(f"业务数据库已初始化：{store.db_url}")


if __name__ == "__main__":
    main()

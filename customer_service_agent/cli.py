"""Command-line entry point for the customer service agent."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from .graph import build_customer_service_graph


def main() -> None:
    graph = build_customer_service_graph()
    print("智能客服已启动，输入 exit 退出。")
    while True:
        question = input("用户> ").strip()
        if question.lower() in {"exit", "quit", "q"}:
            print("客服> 感谢咨询，再见！")
            return
        result = graph.invoke({"messages": [HumanMessage(content=question)]})
        print(f"客服> {result['answer']}")


if __name__ == "__main__":
    main()

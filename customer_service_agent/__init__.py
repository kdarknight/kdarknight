"""LangChain + LangGraph powered customer service agent."""

__all__ = ["build_customer_service_graph"]


def build_customer_service_graph(*args, **kwargs):
    """Lazily import the LangGraph builder so data modules can be used alone."""

    from .graph import build_customer_service_graph as _build_customer_service_graph

    return _build_customer_service_graph(*args, **kwargs)

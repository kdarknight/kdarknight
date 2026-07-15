"""Knowledge base primitives for the customer service agent."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from langchain_core.documents import Document


FAQ_DOCUMENTS: list[Document] = [
    Document(
        page_content=(
            "退货退款政策：签收后 7 天内，商品保持完好且不影响二次销售，可申请无理由退货。"
            "质量问题支持 30 天内免费退换。退款会在仓库验收后 1-3 个工作日原路返回。"
        ),
        metadata={"topic": "refund"},
    ),
    Document(
        page_content=(
            "物流时效：普通快递通常 2-5 天送达，偏远地区可能延长 1-3 天。"
            "订单发货后会通过短信和站内信发送运单号。"
        ),
        metadata={"topic": "shipping"},
    ),
    Document(
        page_content=(
            "会员权益：银卡会员享 98 折，金卡会员享 95 折并免基础运费，"
            "黑金会员享 92 折、专属客服和每月一次优先换货。"
        ),
        metadata={"topic": "membership"},
    ),
    Document(
        page_content=(
            "发票说明：订单完成后 30 天内可在订单详情页申请电子发票。"
            "企业抬头需填写纳税人识别号，发票通常 24 小时内开具。"
        ),
        metadata={"topic": "invoice"},
    ),
]


@dataclass(frozen=True)
class SimpleKnowledgeBase:
    """A tiny dependency-free retriever suitable for demos and tests.

    Production deployments can replace this class with a vector store retriever
    without changing the LangGraph orchestration code.
    """

    documents: tuple[Document, ...] = tuple(FAQ_DOCUMENTS)

    def retrieve(self, query: str, limit: int = 2) -> list[Document]:
        scored = sorted(
            self.documents,
            key=lambda doc: _score(query, doc.page_content + str(doc.metadata)),
            reverse=True,
        )
        return scored[:limit]


def _score(query: str, text: str) -> float:
    query_chars = set(query.lower())
    text_lower = text.lower()
    overlap = sum(1 for char in query_chars if char in text_lower)
    ratio = SequenceMatcher(None, query.lower(), text_lower).ratio()
    return overlap + ratio

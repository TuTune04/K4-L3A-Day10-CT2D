from __future__ import annotations

from dataclasses import dataclass
import re

from core.config import Settings
from core.utils import first_sentence
from retrieval.index import LocalEmbeddingIndex, SearchResult


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_contexts: list[str]
    retrieved_titles: list[str]


def _shared_categories(results: list[SearchResult]) -> str:
    """Multi-hop: giao cac linh vuc cua nhung bai duoc nhac ten trong cau hoi."""
    category_sets = [[item.strip() for item in result.metadata["categories_joined"].split(",") if item.strip()] for result in results]
    shared = [category for category in category_sets[0] if all(category in others for others in category_sets[1:])]
    return ", ".join(shared) if shared else "No shared categories found."


def _extract_answer(question: str, top_result: SearchResult, named_results: list[SearchResult] | None = None) -> str:
    lowered = question.lower()
    metadata = top_result.metadata
    if "in common" in lowered and named_results and len(named_results) >= 2:
        return _shared_categories(named_results)
    if "who authored" in lowered or "list the authors" in lowered:
        return metadata["authors_joined"]
    if "when was" in lowered or "publication date" in lowered or "published on" in lowered:
        return metadata["published"]
    if "what categories" in lowered:
        return metadata["categories_joined"]
    return first_sentence(metadata["summary"])


def answer_question(question: str, settings: Settings, index: LocalEmbeddingIndex, top_k: int | None = None) -> AnswerResult:
    # Moi title trong dau nhay don duoc tra cuu chinh xac (cau multi-hop co 2 title).
    exacts = [match for match in (index.lookup(title) for title in re.findall(r"'([^']+)'", question)) if match]
    named_results = [
        SearchResult(
            paper_id=exact["paper_id"],
            title=exact["title"],
            score=1.0,
            content=exact["content"],
            metadata=exact["metadata"],
        )
        for exact in exacts
    ]
    retrieved = index.search(question, top_k=top_k)
    if named_results:
        named_ids = {item.paper_id for item in named_results}
        deduped = named_results + [item for item in retrieved if item.paper_id not in named_ids]
        retrieved = deduped[: (top_k or settings.top_k)]
    if not retrieved:
        answer = "I don't know from the indexed corpus."
    else:
        answer = _extract_answer(question, retrieved[0], named_results)
    return AnswerResult(
        question=question,
        answer=answer,
        retrieved_doc_ids=[item.paper_id for item in retrieved],
        retrieved_contexts=[item.content for item in retrieved],
        retrieved_titles=[item.title for item in retrieved],
    )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd

from core.config import Settings
from core.utils import read_json, safe_slug, write_json
from retrieval.embeddings import MiniLMEmbeddings


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any]


class LocalEmbeddingIndex:
    def __init__(
        self,
        settings: Settings,
        collection_name: str | None = None,
        documents: list[dict[str, Any]] | None = None,
        persist_path: Path | None = None,
    ):
        self.settings = settings
        self.collection_name = collection_name or settings.baseline_collection_name
        self.persist_path = persist_path or settings.paths.chroma_dir
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self.embedding_backend = "chroma"
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
        self._set_documents(documents or [])

    def _set_documents(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.documents_by_paper_id = {document["paper_id"].lower(): document for document in documents}
        self.documents_by_title = {document["title"].lower(): document for document in documents}

    @staticmethod
    def _build_documents(df: pd.DataFrame) -> list[dict[str, Any]]:
        records = df.to_dict(orient="records")
        documents: list[dict[str, Any]] = []
        for index, row in enumerate(records):
            documents.append(
                {
                    "record_id": f"{row['paper_id']}::{index}",
                    "paper_id": row["paper_id"],
                    "title": row["title"],
                    "content": row["text_for_embedding"],
                    "metadata": {
                        "paper_id": row["paper_id"],
                        "title": row["title"],
                        "published": row["published"],
                        "authors_joined": row["authors_joined"],
                        "categories_joined": row["categories_joined"],
                        "summary": row["summary"],
                        "abs_url": row["abs_url"],
                        "pdf_url": row["pdf_url"],
                    },
                }
            )
        return documents

    @staticmethod
    def _derive_collection_name(settings: Settings, embeddings_output_path: Path | None) -> str:
        if embeddings_output_path is None:
            return settings.baseline_collection_name

        name_map = {
            settings.paths.embeddings_json.resolve(): settings.baseline_collection_name,
            settings.paths.corrupted_embeddings_json.resolve(): settings.corrupted_collection_name,
            settings.paths.repaired_embeddings_json.resolve(): settings.repaired_collection_name,
        }
        resolved_path = embeddings_output_path.resolve()
        if resolved_path in name_map:
            return name_map[resolved_path]
        return safe_slug(embeddings_output_path.stem)

    def _portable_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.settings.paths.project_dir).as_posix()
        except ValueError:
            return str(path)

    def _index_documents(self, documents: list[dict[str, Any]], manifest_path: Path) -> None:
        """Tao lai collection tu dau (idempotent) roi nap embedding + metadata."""
        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            pass
        self.collection = self.client.create_collection(
            name=self.collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
        embeddings = self.embedding_model.embed_documents([document["content"] for document in documents])
        self.collection.add(
            ids=[document["record_id"] for document in documents],
            embeddings=embeddings,
            documents=[document["content"] for document in documents],
            metadatas=[document["metadata"] for document in documents],
        )
        self._set_documents(documents)
        write_json(
            manifest_path,
            {
                "backend": "chroma",
                "embedding_model": self.settings.embedding_model,
                # Luu duong dan tuong doi voi project de manifest chay duoc tren may khac.
                "persist_path": self._portable_path(self.persist_path),
                "collection_name": self.collection_name,
                "documents": documents,
            },
        )

    @classmethod
    def build(
        cls,
        df: pd.DataFrame,
        settings: Settings,
        embeddings_output_path: Path | None = None,
    ) -> "LocalEmbeddingIndex":
        collection_name = cls._derive_collection_name(settings, embeddings_output_path)
        index = cls(settings=settings, collection_name=collection_name)
        index._index_documents(cls._build_documents(df), embeddings_output_path or settings.paths.embeddings_json)
        return index

    def build_from_clean(self, clean_json_path: Path | None = None) -> "LocalEmbeddingIndex":
        """Nap `data/clean/papers_clean.json` vao collection hien tai (dung cho smoke test CP2)."""
        df = pd.DataFrame(read_json(clean_json_path or self.settings.paths.clean_json))
        manifest_path = {
            self.settings.baseline_collection_name: self.settings.paths.embeddings_json,
            self.settings.corrupted_collection_name: self.settings.paths.corrupted_embeddings_json,
            self.settings.repaired_collection_name: self.settings.paths.repaired_embeddings_json,
        }.get(self.collection_name, self.settings.paths.embeddings_json.with_name(f"{self.collection_name}.json"))
        self._index_documents(self._build_documents(df), manifest_path)
        return self

    @classmethod
    def load(cls, settings: Settings, embeddings_path: Path | None = None) -> "LocalEmbeddingIndex":
        payload = read_json(embeddings_path or settings.paths.embeddings_json)
        return cls(
            settings=settings,
            collection_name=payload["collection_name"],
            documents=payload["documents"],
            persist_path=settings.paths.project_dir / payload["persist_path"],
        )

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        query_embedding = self.embedding_model.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k or self.settings.top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        scored: list[SearchResult] = []
        for record_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            if not record_id or not metadata or not content:
                continue
            scored.append(
                SearchResult(
                    paper_id=str(metadata["paper_id"]),
                    title=str(metadata["title"]),
                    score=max(0.0, 1.0 - float(distance or 0.0)),
                    content=str(content),
                    metadata=dict(metadata),
                )
            )
        return scored

    def semantic_search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        return self.search(query, top_k=top_k)

    def lookup(self, value: str) -> dict[str, Any] | None:
        needle = value.strip().lower()
        if needle in self.documents_by_paper_id:
            return self.documents_by_paper_id[needle]
        if needle in self.documents_by_title:
            return self.documents_by_title[needle]
        return None

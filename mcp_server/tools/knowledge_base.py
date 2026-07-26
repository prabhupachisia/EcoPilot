from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
import uuid
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
from fastmcp import FastMCP

if TYPE_CHECKING:
    # DependencyProvider constructs a KnowledgeBase — importing it at
    # runtime here would be circular.
    from mcp_server.dependencies import DependencyProvider


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100


@dataclass(slots=True)
class Document:
    id: str
    name: str
    path: Path
    text: str
    source: str
    category: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentChunk:
    id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchResult:
    chunk: DocumentChunk
    document: Document
    score: float


class KnowledgeBase:
    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        model: "SentenceTransformer | None" = None,
    ) -> None:
        self.embedding_model_name = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # SentenceTransformer(...) downloads the model on first use, so we
        # hold off until embed_chunks/embed_query actually need it instead
        # of doing it here unconditionally. Tests can pass a fake encoder
        # via model=.
        self._model = model

        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, DocumentChunk] = {}

        self.embeddings: np.ndarray | None = None
        self.index: faiss.Index | None = None

        self.chunk_order: list[str] = []

    @property
    def model(self) -> "SentenceTransformer":
        if self._model is None:
            self._model = SentenceTransformer(self.embedding_model_name)
        return self._model

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def indexed(self) -> bool:
        return self.index is not None

    def clear(self) -> None:
        self.documents.clear()
        self.chunks.clear()

        self.embeddings = None
        self.index = None

        self.chunk_order.clear()

    def load_document(
        self,
        path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(path)

        metadata = metadata or {}

        document = Document(
            id=str(uuid.uuid4()),
            name=path.stem,
            path=path,
            text=path.read_text(
                encoding="utf-8",
                errors="ignore",
            ),
            source=str(path),
            category=metadata.get("category", "general"),
            metadata=metadata,
        )

        self.documents[document.id] = document

        self._chunk_document(document)

        return document


    def load_directory(
        self,
        directory: str | Path,
        pattern: str = "*.txt",
    ) -> list[Document]:
        directory = Path(directory)

        documents: list[Document] = []

        for file in sorted(directory.rglob(pattern)):
            documents.append(
                self.load_document(file)
            )

        return documents


    def load_documents(
        self,
        paths: list[str | Path],
    ) -> list[Document]:
        documents: list[Document] = []

        for path in paths:
            path = Path(path)

            if path.is_dir():
                documents.extend(
                    self.load_directory(path)
                )
            else:
                documents.append(
                    self.load_document(path)
                )

        return documents


    def _chunk_document(
        self,
        document: Document,
    ) -> None:
        chunks = self._chunk_text(
            document.text,
        )

        for text in chunks:
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                text=text,
                metadata=document.metadata.copy(),
            )

            self.chunks[chunk.id] = chunk
            self.chunk_order.append(chunk.id)


    def _chunk_text(
        self,
        text: str,
    ) -> list[str]:
        if not text.strip():
            return []

        words = text.split()

        chunks: list[str] = []

        step = max(
            1,
            self.chunk_size - self.chunk_overlap,
        )

        for start in range(
            0,
            len(words),
            step,
        ):
            end = start + self.chunk_size

            chunk = " ".join(
                words[start:end]
            )

            if chunk.strip():
                chunks.append(chunk)

        return chunks

    def embed_chunks(
        self,
    ) -> np.ndarray:
        if not self.chunks:
            raise ValueError(
                "No document chunks available."
            )

        texts = [
            self.chunks[chunk_id].text
            for chunk_id in self.chunk_order
        ]

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        ).astype(np.float32)

        self.dimension = embeddings.shape[1]

        return embeddings


    def build_index(
        self,
    ) -> None:
        embeddings = self.embed_chunks()

        self.index = faiss.IndexFlatIP(
            self.dimension
        )

        self.index.add(embeddings)


    def rebuild_index(
        self,
    ) -> None:
        self.index = None
        self.build_index()

    def embed_query(
        self,
        query: str,
    ) -> np.ndarray:
        embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)

        return embedding

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        if self.index is None:
            raise ValueError(
                "Knowledge base has not been indexed."
            )

        query_embedding = self.embed_query(query)

        scores, indices = self.index.search(
            query_embedding,
            top_k,
        )

        results: list[SearchResult] = []

        for score, index in zip(scores[0], indices[0]):
            if index == -1:
                continue

            chunk_id = self.chunk_order[index]
            chunk = self.chunks[chunk_id]
            document = self.documents[chunk.document_id]

            results.append(
                SearchResult(
                    chunk=chunk,
                    document=document,
                    score=float(score),
                )
            )

        return results

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[str]:
        return [
            result.chunk.text
            for result in self.search(
                query,
                top_k,
            )
        ]

    def search_by_document(
        self,
        document_id: str,
    ) -> list[DocumentChunk]:
        return [
            chunk
            for chunk in self.chunks.values()
            if chunk.document_id == document_id
        ]

    def search_by_category(
        self,
        category: str,
    ) -> list[Document]:
        return [
            document
            for document in self.documents.values()
            if document.metadata.get("category") == category
        ]

    def get_document(
        self,
        document_id: str,
    ) -> Document:
        return self.documents[document_id]

    def get_chunk(
        self,
        chunk_id: str,
    ) -> DocumentChunk:
        return self.chunks[chunk_id]

    def save(
        self,
        directory: str | Path,
    ) -> None:
        if self.index is None:
            raise ValueError(
                "Knowledge base has not been indexed."
            )

        directory = Path(directory)
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        faiss.write_index(
            self.index,
            str(directory / "knowledge.index"),
        )

        metadata = {
            "documents": [
                {
                    "id": document.id,
                    "name": document.name,
                    "path": str(document.path),
                    "source": document.source,
                    "category": document.category,
                    "metadata": document.metadata,
                }
                for document in self.documents.values()
            ],
            "chunks": [
                {
                    "id": chunk.id,
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                }
                for chunk in self.chunks.values()
            ],
            "chunk_order": self.chunk_order,
            "dimension": self.dimension,
            "embedding_model": self.embedding_model_name,
        }

        (directory / "metadata.json").write_text(
            json.dumps(metadata, indent=4),
            encoding="utf-8",
        )

    def load(
        self,
        directory: str | Path,
    ) -> None:
        directory = Path(directory)

        self.index = faiss.read_index(
            str(directory / "knowledge.index")
        )

        metadata = json.loads(
            (directory / "metadata.json").read_text(
                encoding="utf-8"
            )
        )

        self.dimension = metadata["dimension"]
        self.chunk_order = metadata["chunk_order"]

        self.documents.clear()
        self.chunks.clear()

        for doc in metadata["documents"]:
            document = Document(
                id=doc["id"],
                name=doc["name"],
                path=Path(doc["path"]),
                text="",
                source=doc.get("source", doc["path"]),
                category=doc.get("category", "general"),
                metadata=doc["metadata"],
            )

            self.documents[document.id] = document

        for chunk in metadata["chunks"]:
            document_chunk = DocumentChunk(
                id=chunk["id"],
                document_id=chunk["document_id"],
                text=chunk["text"],
                metadata=chunk["metadata"],
            )

            self.chunks[document_chunk.id] = document_chunk

    def statistics(
        self,
    ) -> dict[str, int]:
        return {
            "documents": self.document_count,
            "chunks": self.chunk_count,
            "indexed": int(self.indexed),
        }

def register_knowledge_tools(
    server: FastMCP,
    dependencies: DependencyProvider,
) -> None:
    """
    Register knowledge base tools with the MCP server.
    """

    kb = dependencies.knowledge_base

    @server.tool(
        name="load_knowledge_document",
        description="Load a document into the knowledge base.",
    )
    def load_knowledge_document(
        path: str,
    ) -> Document:
        return kb.load_document(path)

    @server.tool(
        name="build_knowledge_index",
        description="Build the FAISS index for the knowledge base.",
    )
    def build_knowledge_index() -> None:
        kb.build_index()

    @server.tool(
        name="rebuild_knowledge_index",
        description="Rebuild the FAISS index.",
    )
    def rebuild_knowledge_index() -> None:
        kb.rebuild_index()

    @server.tool(
        name="search_knowledge",
        description="Search the knowledge base using semantic similarity.",
    )
    def search_knowledge(
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        return kb.search(
            query=query,
            top_k=top_k,
        )

    @server.tool(
        name="retrieve_context",
        description="Retrieve the most relevant context for a query.",
    )
    def retrieve_context(
        query: str,
        top_k: int = 5,
    ) -> list[str]:
        return kb.retrieve(
            query=query,
            top_k=top_k,
        )

    @server.tool(
        name="knowledge_statistics",
        description="Return knowledge base statistics.",
    )
    def knowledge_statistics() -> dict[str, int]:
        return kb.statistics()

    @server.tool(
        name="clear_knowledge_base",
        description="Remove all loaded documents and the search index.",
    )
    def clear_knowledge_base() -> None:
        kb.clear()

__all__ = [
    "Document",
    "DocumentChunk",
    "SearchResult",
    "KnowledgeBase",
]


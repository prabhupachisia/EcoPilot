from pathlib import Path

import numpy as np
import pytest

from mcp_server.tools.knowledge_base import Document, KnowledgeBase, SearchResult


class FakeEncoder:
    """A tiny, deterministic stand-in for SentenceTransformer.

    Avoids downloading a real embedding model in tests: encodes each text
    into a small keyword-presence vector so similarity search still behaves
    sensibly.
    """

    def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False):
        vectors = []

        for text in texts:
            lower = text.lower()
            vector = np.array(
                [
                    1.0 if "ashrae" in lower else 0.0,
                    1.0 if "comfort" in lower else 0.0,
                    1.0 if "energyplus" in lower else 0.0,
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)

            if norm > 0:
                vector = vector / norm

            vectors.append(vector)

        return np.array(vectors, dtype=np.float32)


@pytest.fixture
def knowledge_base() -> KnowledgeBase:
    return KnowledgeBase(model=FakeEncoder())


def test_model_is_not_constructed_until_first_access() -> None:
    knowledge_base = KnowledgeBase()

    assert knowledge_base._model is None


def test_injected_model_is_used_as_is(knowledge_base: KnowledgeBase) -> None:
    assert isinstance(knowledge_base.model, FakeEncoder)


def test_load_document(knowledge_base: KnowledgeBase, tmp_path: Path) -> None:
    document_path = tmp_path / "ashrae.txt"
    document_path.write_text("ASHRAE defines thermal comfort bounds.")

    document = knowledge_base.load_document(document_path)

    assert document.name == "ashrae"
    assert knowledge_base.document_count == 1
    assert knowledge_base.chunk_count == 1


def test_search_returns_result_with_populated_document_field(
    knowledge_base: KnowledgeBase, tmp_path: Path
) -> None:
    """Regression test: SearchResult previously had no ``document`` field,
    even though ``search()`` always constructed it with one."""

    comfort_doc = tmp_path / "comfort.txt"
    comfort_doc.write_text("ASHRAE 55 defines occupant thermal comfort.")

    energy_doc = tmp_path / "energyplus.txt"
    energy_doc.write_text("EnergyPlus simulates building energy use.")

    knowledge_base.load_document(comfort_doc)
    knowledge_base.load_document(energy_doc)
    knowledge_base.build_index()

    results = knowledge_base.search("comfort", top_k=2)

    assert len(results) == 2
    assert all(isinstance(result, SearchResult) for result in results)
    assert all(isinstance(result.document, Document) for result in results)

    top_result = results[0]
    assert "comfort" in top_result.chunk.text.lower()
    assert top_result.document.name == "comfort"


def test_retrieve_returns_chunk_text_only(knowledge_base: KnowledgeBase, tmp_path: Path) -> None:
    document_path = tmp_path / "doc.txt"
    document_path.write_text("EnergyPlus reference documentation.")

    knowledge_base.load_document(document_path)
    knowledge_base.build_index()

    results = knowledge_base.retrieve("energyplus", top_k=1)

    assert results == ["EnergyPlus reference documentation."]


def test_statistics(knowledge_base: KnowledgeBase, tmp_path: Path) -> None:
    document_path = tmp_path / "doc.txt"
    document_path.write_text("Some content.")

    knowledge_base.load_document(document_path)

    stats = knowledge_base.statistics()

    assert stats["documents"] == 1
    assert stats["chunks"] == 1
    assert stats["indexed"] == 0

    knowledge_base.build_index()

    assert knowledge_base.statistics()["indexed"] == 1


def test_clear_resets_everything(knowledge_base: KnowledgeBase, tmp_path: Path) -> None:
    document_path = tmp_path / "doc.txt"
    document_path.write_text("Some content.")

    knowledge_base.load_document(document_path)
    knowledge_base.build_index()

    knowledge_base.clear()

    assert knowledge_base.document_count == 0
    assert knowledge_base.chunk_count == 0
    assert knowledge_base.indexed is False

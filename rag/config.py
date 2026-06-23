"""RAG configuration loaded from settings.yaml with env overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

_SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


@dataclass(frozen=True)
class HybridSettings:
    """Hybrid BM25 + dense retrieval settings."""

    enabled: bool = True
    retrieve_k: int = 30
    rrf_k: int = 60
    fusion_top_n: int = 50


@dataclass(frozen=True)
class MemoryRetrieveSettings:
    """Memory corpus retrieval settings."""

    retrieve_k: int = 20
    fusion_top_n: int = 30


@dataclass(frozen=True)
class RerankSettings:
    """Two-stage rerank settings."""

    enabled: bool = True
    stage1_top_n: int = 20
    stage2_top_n: int = 5
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    batch_size: int = 16


@dataclass(frozen=True)
class RewriteSettings:
    """Query rewrite settings."""

    enabled: bool = True
    max_recent_messages: int = 6


@dataclass(frozen=True)
class InjectSettings:
    """Prompt injection settings."""

    planner: bool = True
    executor: bool = True


@dataclass(frozen=True)
class ExtractSettings:
    """Memory extraction ingest settings."""

    min_importance: float = 0.3
    dedup_threshold: float = 0.92


@dataclass(frozen=True)
class MemoryStoreSettings:
    """Memory persistence backend settings."""

    backend: str = "faiss"
    embedding_dim: int = 1536
    database_url: str | None = None


@dataclass(frozen=True)
class RagSettings:
    """Top-level RAG configuration."""

    enabled: bool = True
    index_dir: Path = field(default_factory=lambda: Path("data/rag"))
    embedding_provider: str = "ollama"
    embedding_model: str = "BGE-M3:latest"
    top_k: int = 5
    hybrid: HybridSettings = field(default_factory=HybridSettings)
    memory: MemoryRetrieveSettings = field(default_factory=MemoryRetrieveSettings)
    memory_store: MemoryStoreSettings = field(default_factory=MemoryStoreSettings)
    rerank: RerankSettings = field(default_factory=RerankSettings)
    rewrite: RewriteSettings = field(default_factory=RewriteSettings)
    inject: InjectSettings = field(default_factory=InjectSettings)
    extract: ExtractSettings = field(default_factory=ExtractSettings)


def _load_yaml() -> dict[str, object]:
    if not _SETTINGS_PATH.is_file():
        return {}
    with _SETTINGS_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _section(data: dict[str, object], key: str) -> dict[str, object]:
    section = data.get(key, {})
    return section if isinstance(section, dict) else {}


def load_rag_settings() -> RagSettings:
    """Load RAG settings from YAML and environment variables."""
    raw = _section(_load_yaml(), "rag")

    hybrid_raw = _section(raw, "hybrid")
    memory_raw = _section(raw, "memory")
    memory_store_raw = _section(raw, "memory_store")
    rerank_raw = _section(raw, "rerank")
    rewrite_raw = _section(raw, "rewrite")
    inject_raw = _section(raw, "inject")
    extract_raw = _section(raw, "extract")

    index_dir = Path(
        os.getenv("RAG_INDEX_DIR", str(raw.get("index_dir", "data/rag")))
    )

    return RagSettings(
        enabled=_env_bool("RAG_ENABLED", bool(raw.get("enabled", True))),
        index_dir=index_dir,
        embedding_provider=os.getenv(
            "EMBEDDING_PROVIDER",
            str(raw.get("embedding_provider", "ollama")),
        ),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL",
            os.getenv(
                "OLLAMA_EMBED_MODEL",
                str(raw.get("embedding_model", "BGE-M3:latest")),
            ),
        ),
        top_k=_env_int("RAG_TOP_K", int(raw.get("top_k", 5))),
        hybrid=HybridSettings(
            enabled=_env_bool(
                "RAG_HYBRID_ENABLED",
                bool(hybrid_raw.get("enabled", True)),
            ),
            retrieve_k=_env_int(
                "RAG_RETRIEVE_K",
                int(hybrid_raw.get("retrieve_k", 30)),
            ),
            rrf_k=_env_int("RAG_RRF_K", int(hybrid_raw.get("rrf_k", 60))),
            fusion_top_n=_env_int(
                "RAG_FUSION_TOP_N",
                int(hybrid_raw.get("fusion_top_n", 50)),
            ),
        ),
        memory=MemoryRetrieveSettings(
            retrieve_k=_env_int(
                "RAG_MEMORY_RETRIEVE_K",
                int(memory_raw.get("retrieve_k", 20)),
            ),
            fusion_top_n=_env_int(
                "RAG_MEMORY_FUSION_TOP_N",
                int(memory_raw.get("fusion_top_n", 30)),
            ),
        ),
        memory_store=MemoryStoreSettings(
            backend=os.getenv(
                "RAG_MEMORY_BACKEND",
                str(memory_store_raw.get("backend", "faiss")),
            ).lower(),
            embedding_dim=_env_int(
                "RAG_MEMORY_EMBEDDING_DIM",
                int(memory_store_raw.get("embedding_dim", 1536)),
            ),
            database_url=os.getenv("DATABASE_URL"),
        ),
        rerank=RerankSettings(
            enabled=_env_bool(
                "RAG_RERANK_ENABLED",
                bool(rerank_raw.get("enabled", True)),
            ),
            stage1_top_n=_env_int(
                "RAG_RERANK_STAGE1_TOP_N",
                int(rerank_raw.get("stage1_top_n", 20)),
            ),
            stage2_top_n=_env_int(
                "RAG_RERANK_STAGE2_TOP_N",
                int(rerank_raw.get("stage2_top_n", 5)),
            ),
            cross_encoder_model=os.getenv(
                "RAG_CROSS_ENCODER_MODEL",
                str(
                    rerank_raw.get(
                        "cross_encoder_model",
                        "cross-encoder/ms-marco-MiniLM-L-6-v2",
                    )
                ),
            ),
            batch_size=_env_int(
                "RAG_RERANK_BATCH_SIZE",
                int(rerank_raw.get("batch_size", 16)),
            ),
        ),
        rewrite=RewriteSettings(
            enabled=_env_bool(
                "RAG_REWRITE_ENABLED",
                bool(rewrite_raw.get("enabled", True)),
            ),
            max_recent_messages=_env_int(
                "RAG_REWRITE_MAX_MESSAGES",
                int(rewrite_raw.get("max_recent_messages", 6)),
            ),
        ),
        inject=InjectSettings(
            planner=_env_bool(
                "RAG_INJECT_PLANNER",
                bool(inject_raw.get("planner", True)),
            ),
            executor=_env_bool(
                "RAG_INJECT_EXECUTOR",
                bool(inject_raw.get("executor", True)),
            ),
        ),
        extract=ExtractSettings(
            min_importance=_env_float(
                "RAG_EXTRACT_MIN_IMPORTANCE",
                float(extract_raw.get("min_importance", 0.3)),
            ),
            dedup_threshold=_env_float(
                "RAG_EXTRACT_DEDUP_THRESHOLD",
                float(extract_raw.get("dedup_threshold", 0.92)),
            ),
        ),
    )

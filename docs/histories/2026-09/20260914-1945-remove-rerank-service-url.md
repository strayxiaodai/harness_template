## [2026-09-14 19:45] | Task: Remove service_url and HTTP reranker code

### User Query
> remove this line and related code: service_url: null # Machine/host IP overrides (e.g. 192.168.x.x) live in .env via RAG_RERANK_URL

### Changes Overview
- Removed `service_url` configuration setting from `config/settings.yaml` and `rag/config.py`.
- Removed `RAG_RERANK_URL` environment variable support.
- Removed HTTP-based remote reranking (`_predict_http` method and `service_url` parameter) from `CrossEncoderReranker` in `rag/retrieve/rerank/cross_encoder.py` and constructor call in `rag/retrieve/rerank/pipeline.py`.
- Removed `RAG_RERANK_URL` from `.env` and `test_cross_encoder_reranker_http` from `tests/test_rag_service.py`.

### Design Intent
Standardized `CrossEncoderReranker` on direct local execution, eliminating unnecessary HTTP/network reranking complexity and unused configuration options.

### Files Modified
- `config/settings.yaml`
- `.env`
- `rag/config.py`
- `rag/retrieve/rerank/cross_encoder.py`
- `rag/retrieve/rerank/pipeline.py`
- `tests/test_rag_service.py`

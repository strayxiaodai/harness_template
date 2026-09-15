## [2026-09-14 20:07] | Task: Implement Docling PDF document loader in rag/ingest/documents.py

### User Query
> implement Docling for @[rag/ingest/documents.py]

### Changes Overview
- Added [`load_pdf_document()`](file:///Users/frank/harness_template/rag/ingest/documents.py) in `rag/ingest/documents.py` using Docling `DocumentConverter` for layout-aware Markdown extraction, with a `pypdf` fallback.
- Updated [`load_documents()`](file:///Users/frank/harness_template/rag/ingest/documents.py) to support PDF files (`**/*.pdf`), directory-wide PDF scanning, and direct single-file ingestion paths.
- Updated [`_extract_topics_from_content()`](file:///Users/frank/harness_template/rag/ingest/documents.py) to extract topic headers from PDF Markdown.
- Added comprehensive unit tests in [`tests/test_ingest_documents.py`](file:///Users/frank/harness_template/tests/test_ingest_documents.py).

### Design Intent
Integrate IBM Docling layout parsing to convert PDF documents into structured Markdown before chunking, while maintaining graceful fallback to `pypdf` if Docling is unavailable.

### Files Modified
- `rag/ingest/documents.py`
- `tests/test_ingest_documents.py`

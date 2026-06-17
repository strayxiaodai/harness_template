"""Format retrieved chunks for prompt injection."""

from __future__ import annotations

from langchain_core.documents import Document


def format_documents(
    documents: list[Document],
    *,
    header: str,
    empty_label: str = "(none)",
) -> str:
    """Format documents into a prompt block.

    Args:
        documents: Retrieved documents.
        header: Section header line.
        empty_label: Text when no documents are found.

    Returns:
        Formatted prompt block.
    """
    if not documents:
        return f"{header}\n{empty_label}"

    lines = [header]
    for doc in documents:
        source = doc.metadata.get("source", doc.metadata.get("memory_type", "?"))
        lines.append(f"- [{source}] {doc.page_content}")
    return "\n".join(lines)


def format_memory_context(documents: list[Document]) -> str:
    """Format memory documents for planner/executor injection."""
    return format_documents(
        documents,
        header="Relevant memories from prior conversations:",
        empty_label="(no relevant memories)",
    )


def format_document_context(documents: list[Document]) -> str:
    """Format static document chunks for tool output."""
    if not documents:
        return "No relevant documents found."
    return format_documents(
        documents,
        header="Retrieved documents:",
        empty_label="No relevant documents found.",
    )

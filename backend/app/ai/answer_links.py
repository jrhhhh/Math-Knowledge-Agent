"""Attach explicit citations and scoped deterministic results to answer paragraphs.

Citation markers only prove that a source was cited, not that it supports a claim.
No semantic match, model confidence, or source availability becomes verification.
"""
import re


TOOL_SOURCES = {"exact_calculus_tool", "polynomial_identity_tool"}


def build_answer_links(answer: str, sources: list[dict], tools: list[dict], answer_source: str) -> list[dict]:
    available = {str(source["chunk_id"]): source for source in sources if source.get("chunk_id") is not None}
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\n(?=结论：|原函数：|依据：|适用范围：|比较对象：|将左侧)", answer or "") if part.strip()]
    steps = []
    deterministic = answer_source in TOOL_SOURCES and any(tool.get("status") in {"computed", "symbolically_verified", "identity_disproved"} for tool in tools)
    for index, paragraph in enumerate(paragraphs, 1):
        mentioned = list(dict.fromkeys(re.findall(r"\[S(\d+)\]", paragraph)))
        source_ids = [int(key) for key in mentioned if key in available]
        missing = [f"S{key}" for key in mentioned if key not in available]
        tool_ids = [i + 1 for i, tool in enumerate(tools) if deterministic and tool.get("status") in {"computed", "symbolically_verified", "identity_disproved"}]
        if answer_source in {"tutor_hint", "local_hint"}:
            status = "teaching_hint"
        elif deterministic:
            status = "scoped_calculation" if not paragraph.startswith(("依据：", "适用范围：")) else "tool_scope"
        elif source_ids:
            status = "source_cited"
        else:
            status = "unverified"
        steps.append({"step": index, "text": paragraph, "status": status,
                      "source_chunk_ids": source_ids, "tool_ids": tool_ids,
                      "unresolved_citations": missing})
    return steps

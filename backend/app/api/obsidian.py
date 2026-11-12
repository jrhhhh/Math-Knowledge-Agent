"""Build a portable Obsidian vault from the saved knowledge graph and notes."""
import json
from collections import defaultdict
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.notes import get_db, note_markdown
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.study_note import StudyNote

router = APIRouter(prefix="/obsidian", tags=["Obsidian"])


def link(path: str, title: str) -> str:
    # Keep the display label from changing the wiki link syntax.
    label = title.replace("[", "［").replace("]", "］").replace("|", "｜")
    return f"[[{path}|{' '.join(label.split()) or path}]]"


@router.get("/vault")
def export_vault(
    graph: bool = True, notes: bool = True, db: Session = Depends(get_db)
):
    if not (graph or notes):
        raise HTTPException(422, detail="请至少选择一类内容")

    concepts = db.query(Concept).order_by(Concept.id).all() if graph else []
    saved_notes = db.query(StudyNote).order_by(StudyNote.id).all() if notes else []
    targets = {item.id: link(f"知识点/concept-{item.id}", item.name) for item in concepts}
    outgoing = defaultdict(list)
    if targets:
        for edge in db.query(ConceptRelation).order_by(ConceptRelation.id):
            target = targets.get(edge.target_concept_id)
            if edge.source_concept_id in targets and target:
                outgoing[edge.source_concept_id].append(f"- {edge.relation} → {target}")

    index = [
        "# Math-Agent 知识库",
        "",
        "在 Obsidian 中打开此文件夹，点击链接浏览知识点和笔记。",
        "知识点页面列出有向关系。可用反向链接查看指向该知识点的页面。",
    ]
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as vault:
        if graph:
            index.extend(["", f"## 知识点（{len(concepts)}）", ""])
            index.extend(f"- {target}" for target in targets.values())
            for item in concepts:
                aliases = json.dumps([item.name], ensure_ascii=False)
                lines = [
                    "---", f"aliases: {aliases}", "---", "",
                    f"# {item.name}", "", f"领域：{item.field or '未分类'}",
                    f"类型：{item.type or 'concept'}", "", item.description or "",
                ]
                if outgoing[item.id]:
                    lines.extend(["", "## 指向的知识点", "", *outgoing[item.id]])
                vault.writestr(f"知识点/concept-{item.id}.md", "\n".join(lines) + "\n")
        if notes:
            index.extend(["", f"## 学习笔记（{len(saved_notes)}）", ""])
            for note in saved_notes:
                path = f"学习笔记/note-{note.id}"
                index.append(f"- {link(path, note.title)}")
                aliases = json.dumps([note.title], ensure_ascii=False)
                properties = (
                    f"---\naliases: {aliases}\n"
                    f"favorite: {str(note.favorite).lower()}\n"
                    f"archived: {str(note.archived).lower()}\n---\n\n"
                )
                vault.writestr(f"{path}.md", properties + note_markdown(note))
        vault.writestr("知识库索引.md", "\n".join(index) + "\n")
    return Response(
        output.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="Math-Agent-Obsidian.zip"',
            "Cache-Control": "no-store",
        },
    )

from app.models.concept_relation import ConceptRelation

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.ai import router as ai_router
from app.api.knowledge import router as knowledge_router

from app.database import engine

from app.models.concept import Base
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.graph_candidate import GraphCandidate
from app.models.concept_alias import ConceptAlias
from app.models.graph_candidate_event import GraphCandidateEvent
from app.models.ai_retry_job import AIRetryJob
from app.models.ai_request_log import AIRequestLog
from app.models.local_template import LocalTemplate
from app.models.local_template_event import LocalTemplateEvent
from app.models.question_sample import QuestionSample
from app.models.template_audit_log import TemplateAuditLog
from app.models.template_audit_archive import TemplateAuditArchive
from app.models.answer_record import AnswerRecord, AnswerFeedback
from app.ai.retry_queue import resume_pending_jobs
from sqlalchemy import inspect, text


from app.api.concepts import router
from app.api.problems import router as problem_router
from app.api.problem_concepts import router as problem_concept_router
from app.api.templates import router as template_router


Base.metadata.create_all(
    bind=engine
)

# 保持旧 SQLite 数据兼容：create_all 不会给已有表补列。
with engine.begin() as connection:
    columns = {column["name"] for column in inspect(connection).get_columns("local_answer_template_events")}
    if "snapshot" not in columns:
        connection.execute(text("ALTER TABLE local_answer_template_events ADD COLUMN snapshot TEXT"))
    template_columns = {column["name"] for column in inspect(connection).get_columns("local_answer_templates")}
    if "review_status" not in template_columns:
        connection.execute(text("ALTER TABLE local_answer_templates ADD COLUMN review_status VARCHAR(20) NOT NULL DEFAULT 'approved'"))
    template_columns = {column["name"] for column in inspect(connection).get_columns("local_answer_templates")}
    if "hit_count" not in template_columns:
        connection.execute(text("ALTER TABLE local_answer_templates ADD COLUMN hit_count INTEGER NOT NULL DEFAULT 0"))
    if "last_hit_at" not in template_columns:
        connection.execute(text("ALTER TABLE local_answer_templates ADD COLUMN last_hit_at DATETIME"))
resume_pending_jobs()


app = FastAPI(
    title="Math Knowledge Agent"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)
app.include_router(knowledge_router)

app.include_router(router)
app.include_router(problem_router)
app.include_router(problem_concept_router)
app.include_router(template_router)


@app.get("/")
def home():
    return {
        "message": "Math Agent is running"
    }

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
from app.models.answer_review import AnswerReview
from app.models.answer_review_event import AnswerReviewEvent
from app.models.security_event import SecurityEvent
from app.models.ai_task_status import AITaskStatus
from app.models.concept_learning_progress import ConceptLearningProgress
from app.models.conversation import Conversation, ConversationMessage, MessageConcept
from app.logging_config import configure_logging
from app.ai.retry_queue import resume_pending_jobs
from app.migrations import run_schema_migrations


from app.api.concepts import router
from app.api.problems import router as problem_router
from app.api.problem_concepts import router as problem_concept_router
from app.api.templates import router as template_router
from app.api.maintenance import router as maintenance_router
from app.api.conversations import router as conversations_router


Base.metadata.create_all(
    bind=engine
)
logger = configure_logging()

# 保持旧 SQLite 数据兼容：create_all 不会给已有表补列。
with engine.begin() as connection:
    run_schema_migrations(connection)
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
app.include_router(maintenance_router)
app.include_router(conversations_router)


@app.get("/")
def home():
    return {
        "message": "Math Agent is running"
    }

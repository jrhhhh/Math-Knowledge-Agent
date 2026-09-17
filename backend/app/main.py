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
from app.ai.retry_queue import resume_pending_jobs


from app.api.concepts import router
from app.api.problems import router as problem_router
from app.api.problem_concepts import router as problem_concept_router


Base.metadata.create_all(
    bind=engine
)
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


@app.get("/")
def home():
    return {
        "message": "Math Agent is running"
    }

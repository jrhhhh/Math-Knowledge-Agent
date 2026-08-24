from fastapi import FastAPI

from app.database import engine

from app.models.concept import Base
from app.models.problem import Problem


from app.api.concepts import router
from app.api.problems import router as problem_router


Base.metadata.create_all(
    bind=engine
)


app = FastAPI(
    title="Math Knowledge Agent"
)


app.include_router(router)
app.include_router(problem_router)


@app.get("/")
def home():
    return {
        "message":"Math Agent is running"
    }
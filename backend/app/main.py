from fastapi import FastAPI

from app.database import engine
from app.models.concept import Base

from app.api.concepts import router


Base.metadata.create_all(
    bind=engine
)


app = FastAPI(
    title="Math Knowledge Agent"
)


app.include_router(router)


@app.get("/")
def home():

    return {
        "message": "Math Agent is running"
    }

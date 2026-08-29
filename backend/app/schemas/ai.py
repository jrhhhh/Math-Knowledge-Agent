from pydantic import BaseModel


class ProblemAnalysisRequest(BaseModel):

    problem_id: int
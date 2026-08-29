from fastapi import APIRouter

from app.ai.analyzer import analyze_problem
from app.schemas.ai import ProblemAnalysisRequest


router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


@router.post("/analyze-problem")
def analyze_math_problem(
    request: ProblemAnalysisRequest
):

    result = analyze_problem(
        request.problem
    )

    return result
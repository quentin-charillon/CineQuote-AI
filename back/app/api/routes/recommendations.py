from fastapi import APIRouter, Depends, Request

from app.models.account import User
from app.schemas.account import RecommendationsResponse
from app.services.auth import get_current_user
from app.services.recommendations import recommendation_service
from app.services.security import security_limiters

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/recommendations", response_model=RecommendationsResponse)
def create_recommendations(request: Request, user: User = Depends(get_current_user)) -> RecommendationsResponse:
    security_limiters.check_ai(request, user.id)
    return recommendation_service.create(user.id)

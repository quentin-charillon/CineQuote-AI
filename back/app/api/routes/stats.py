from fastapi import APIRouter, Depends

from app.models.account import User
from app.schemas.account import UserStatsResponse
from app.services.auth import get_current_user
from app.services.stats import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/me", response_model=UserStatsResponse)
def my_stats(user: User = Depends(get_current_user)) -> UserStatsResponse:
    return stats_service.get(user.id)

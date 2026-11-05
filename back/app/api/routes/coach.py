from fastapi import APIRouter, Depends, Request

from app.models.account import User
from app.schemas.account import CoachResponse
from app.services.auth import get_current_user
from app.services.coach import coach_service
from app.services.security import security_limiters

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/coach", response_model=CoachResponse)
def create_coaching_note(request: Request, user: User = Depends(get_current_user)) -> CoachResponse:
    security_limiters.check_ai(request, user.id)
    return coach_service.create(user.id)

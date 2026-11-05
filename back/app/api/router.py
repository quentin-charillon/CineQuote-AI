from fastapi import APIRouter

from app.api.routes import auth, coach, health, quiz, recommendations, stats

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(quiz.router)
api_router.include_router(auth.router)
api_router.include_router(stats.router)
api_router.include_router(coach.router)
api_router.include_router(recommendations.router)


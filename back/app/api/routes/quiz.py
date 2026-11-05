from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.models.account import User
from app.services.auth import get_optional_user
from app.services.security import security_limiters

from app.schemas.quiz import (
    AnswerResult,
    AnswerSubmission,
    HintRequest,
    HintResponse,
    ExplanationRequest,
    ExplanationResponse,
    DifficultyAvailability,
    QuizAvailability,
    PublicQuestion,
    QuizResults,
    SessionCreated,
    SessionCreateRequest,
    CustomSessionRequest,
    CustomSessionCreated,
)
from app.services.custom_quiz import custom_quiz_planner
from app.services.quiz import (
    DatasetValidationError,
    InvalidAnswerError,
    HintAlreadyUsedError,
    ExplanationUnavailableError,
    QuizCompletedError,
    QuizNotCompletedError,
    QuizService,
    SessionNotFoundError,
    StaleQuestionError,
    get_quiz_service,
)

router = APIRouter(prefix="/quiz/sessions", tags=["quiz"])


@router.get("/difficulties", response_model=list[DifficultyAvailability])
def list_difficulties(
    service: QuizService = Depends(get_quiz_service),
) -> list[DifficultyAvailability]:
    return service.list_difficulties()


@router.get("/availability", response_model=list[QuizAvailability])
def list_availability(service: QuizService = Depends(get_quiz_service)) -> list[QuizAvailability]:
    return service.list_availability()


@router.post("", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
def create_session(
    request: SessionCreateRequest,
    user: User | None = Depends(get_optional_user),
    service: QuizService = Depends(get_quiz_service),
) -> SessionCreated:
    try:
        return service.create_session(request.difficulty, request.genre, user.id if user else None)
    except DatasetValidationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/custom", response_model=CustomSessionCreated, status_code=status.HTTP_201_CREATED)
def create_custom_session(
    request: CustomSessionRequest,
    http_request: Request,
    user: User | None = Depends(get_optional_user),
    service: QuizService = Depends(get_quiz_service),
) -> CustomSessionCreated:
    security_limiters.check_ai(http_request, user.id if user else None)
    plan = custom_quiz_planner.plan(request.prompt)
    try:
        created = service.create_custom_session(plan.difficulty, list(plan.genres), user.id if user else None)
    except DatasetValidationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    genre_text = " + ".join(genre.replace("_", " ").title() for genre in plan.genres)
    return CustomSessionCreated(
        **created.model_dump(), difficulty=plan.difficulty, genres=list(plan.genres),
        interpretation=f"{plan.difficulty.title()} · {genre_text}", fallback_used=plan.fallback_used,
    )


@router.get("/{session_id}/question", response_model=PublicQuestion)
def get_current_question(
    session_id: str,
    service: QuizService = Depends(get_quiz_service),
) -> PublicQuestion:
    try:
        return service.get_current_question(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Quiz session not found") from error
    except QuizCompletedError as error:
        raise HTTPException(status_code=409, detail="Quiz session is complete") from error


@router.post("/{session_id}/hint", response_model=HintResponse)
def get_hint(
    session_id: str,
    request: HintRequest,
    http_request: Request,
    user: User | None = Depends(get_optional_user),
    service: QuizService = Depends(get_quiz_service),
) -> HintResponse:
    security_limiters.check_ai(http_request, user.id if user else None)
    try:
        return service.get_hint(session_id, request)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Quiz session not found") from error
    except QuizCompletedError as error:
        raise HTTPException(status_code=409, detail="Quiz session is complete") from error
    except StaleQuestionError as error:
        raise HTTPException(status_code=409, detail="Question is no longer current") from error
    except HintAlreadyUsedError as error:
        raise HTTPException(status_code=409, detail="A hint was already used for this question") from error


@router.post("/{session_id}/explanation", response_model=ExplanationResponse)
def get_explanation(
    session_id: str,
    request: ExplanationRequest,
    http_request: Request,
    user: User | None = Depends(get_optional_user),
    service: QuizService = Depends(get_quiz_service),
) -> ExplanationResponse:
    security_limiters.check_ai(http_request, user.id if user else None)
    try:
        return service.get_explanation(session_id, request)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Quiz session not found") from error
    except ExplanationUnavailableError as error:
        raise HTTPException(status_code=409, detail="An explanation is available only after answering this question") from error


@router.post("/{session_id}/answers", response_model=AnswerResult)
def submit_answer(
    session_id: str,
    submission: AnswerSubmission,
    service: QuizService = Depends(get_quiz_service),
) -> AnswerResult:
    try:
        return service.submit_answer(session_id, submission)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Quiz session not found") from error
    except QuizCompletedError as error:
        raise HTTPException(status_code=409, detail="Quiz session is complete") from error
    except StaleQuestionError as error:
        raise HTTPException(status_code=409, detail="Question is no longer current") from error
    except InvalidAnswerError as error:
        raise HTTPException(status_code=400, detail="Answer must be one of the available choices") from error


@router.get("/{session_id}/results", response_model=QuizResults)
def get_results(
    session_id: str,
    service: QuizService = Depends(get_quiz_service),
) -> QuizResults:
    try:
        return service.get_results(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Quiz session not found") from error
    except QuizNotCompletedError as error:
        raise HTTPException(status_code=409, detail="Quiz session is not complete") from error


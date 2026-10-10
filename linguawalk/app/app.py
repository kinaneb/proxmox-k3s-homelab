import secrets
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, status

from config import API_KEY
from consolidation import consolidate_due_periods
from db import get_db, init_db, utc_now
from learning import (
    end_session,
    get_learning_targets,
    load_learning_progress,
    load_learner_profile,
    record_grammar_event,
    record_vocabulary_event,
)
from models import (
    EndSessionRequest,
    EndSessionResult,
    GrammarEventRequest,
    GrammarEventResult,
    LearnerProfile,
    LearningProgress,
    LearningTargets,
    MaintenanceState,
    StartSessionRequest,
    StartSessionResponse,
    VocabularyEventRequest,
    VocabularyEventResult,
)

app = FastAPI(
    title="LinguaWalk API",
    version="3.1.0",
    description="Persistent learning memory for the LinguaWalk custom GPT.",
)


@app.on_event("startup")
def startup() -> None:
    init_db()


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {API_KEY}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get(
    "/profile",
    response_model=LearnerProfile,
    dependencies=[Depends(require_api_key)],
)
def profile() -> LearnerProfile:
    with get_db() as db:
        return load_learner_profile(db)


@app.get(
    "/progress",
    response_model=LearningProgress,
    dependencies=[Depends(require_api_key)],
)
def progress() -> LearningProgress:
    generated_at = utc_now()
    with get_db() as db:
        return load_learning_progress(db, generated_at=generated_at)


@app.get(
    "/learning/targets",
    response_model=LearningTargets,
    dependencies=[Depends(require_api_key)],
)
def learning_targets() -> LearningTargets:
    as_of = utc_now()
    with get_db() as db:
        return get_learning_targets(db, as_of=as_of)


@app.post(
    "/session/start",
    response_model=StartSessionResponse,
    dependencies=[Depends(require_api_key)],
)
def start_session(request: StartSessionRequest) -> StartSessionResponse:
    session_id = str(uuid.uuid4())
    started_at = utc_now()
    started_date = datetime.fromisoformat(started_at).date()

    with get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        rollover = consolidate_due_periods(
            db,
            today=started_date,
            consolidated_at=started_at,
        )
        db.execute(
            """
            INSERT INTO sessions (
                id, started_at, primary_language, secondary_language,
                session_type, initial_subject
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                started_at,
                request.primary_language,
                request.secondary_language,
                request.session_type,
                request.session_subject,
            ),
        )

        profile = load_learner_profile(db)
        targets = get_learning_targets(db, as_of=started_at)

    return StartSessionResponse(
        session_id=session_id,
        learner_profile=profile,
        targets=targets,
        maintenance=MaintenanceState(
            weekly_consolidation_performed=rollover.weekly_consolidation_performed,
            monthly_consolidation_performed=rollover.monthly_consolidation_performed,
        ),
    )


@app.post(
    "/session/end",
    response_model=EndSessionResult,
    dependencies=[Depends(require_api_key)],
)
def close_session(request: EndSessionRequest) -> EndSessionResult:
    try:
        with get_db() as db:
            return end_session(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/vocabulary/event",
    response_model=VocabularyEventResult,
    dependencies=[Depends(require_api_key)],
)
def vocabulary_event(request: VocabularyEventRequest) -> VocabularyEventResult:
    try:
        with get_db() as db:
            return record_vocabulary_event(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/grammar/event",
    response_model=GrammarEventResult,
    dependencies=[Depends(require_api_key)],
)
def grammar_event(request: GrammarEventRequest) -> GrammarEventResult:
    try:
        with get_db() as db:
            return record_grammar_event(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

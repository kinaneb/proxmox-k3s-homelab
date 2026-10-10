from typing import Literal
from pydantic import BaseModel, Field

Language = Literal["FRENCH", "ENGLISH"]
SessionType = Literal["MORNING_WALK", "GENERAL_CONVERSATION", "REVIEW"]


class StartSessionRequest(BaseModel):
    primary_language: Language = "FRENCH"
    secondary_language: Language | None = "ENGLISH"
    session_type: SessionType = "MORNING_WALK"
    session_subject: str | None = "Daily news recap"


class VocabularyTarget(BaseModel):
    key: str
    language: Language
    status: Literal["NOT_LEARNED", "LEARNING", "LEARNED"]
    mastery_level: int = Field(ge=1, le=5)
    difficulty: int = Field(ge=1, le=5)
    priority: float = 0.0
    last_seen: str | None = None
    last_mistake: str | None = None
    next_review_at: str | None = None
    recommended_method: str | None = None
    reason: str | None = None


class GrammarTarget(BaseModel):
    key: str
    display_name: str | None = None
    usefulness_score: int = Field(ge=1, le=5)
    correct_usage_count: int = 0
    mistake_count: int = 0
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    priority_score: float = 0.0
    status: Literal["ACTIVE", "IMPROVING", "STABLE"]
    last_mistake: str | None = None
    last_success: str | None = None
    next_review_at: str | None = None
    recommended_method: str | None = None
    reason: str | None = None


class LearningTargets(BaseModel):
    vocabulary: list[VocabularyTarget] = []
    grammar: list[GrammarTarget] = []


class LearnerProfile(BaseModel):
    baseline_date: str | None = None
    baseline_french_cefr: str | None = None
    overall_french_cefr: str | None = None
    speaking_cefr: str | None = None
    grammar_cefr: str | None = None
    vocabulary_cefr: str | None = None
    listening_cefr: str | None = None
    fluency_cefr: str | None = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    best_learning_methods: list[str] = []
    weak_learning_methods: list[str] = []
    baseline: dict | None = None
    active_vocabulary_count: int = 0
    learned_vocabulary_count: int = 0
    active_grammar_count: int = 0
    stable_grammar_count: int = 0


class WeeklyProgressSummary(BaseModel):
    week: str
    start_date: str
    end_date: str
    session_count: int = 0
    vocabulary_learning: int = 0
    vocabulary_learned: int = 0
    vocabulary_mistakes: int = 0
    active_grammar: int = 0
    improving_grammar: int = 0
    stable_grammar: int = 0
    grammar_mistakes: int = 0
    consolidated_at: str


class MonthlyProgressSummary(BaseModel):
    month: str
    session_count: int = 0
    vocabulary_learning: int = 0
    vocabulary_learned: int = 0
    vocabulary_mistakes: int = 0
    active_grammar: int = 0
    improving_grammar: int = 0
    stable_grammar: int = 0
    grammar_mistakes: int = 0
    french_cefr: str | None = None
    consolidated_at: str


class LearningProgress(BaseModel):
    generated_at: str
    total_sessions: int = 0
    completed_sessions: int = 0
    vocabulary_event_count: int = 0
    grammar_event_count: int = 0
    vocabulary_not_learned: int = 0
    vocabulary_learning: int = 0
    vocabulary_learned: int = 0
    vocabulary_mistakes_total: int = 0
    grammar_active: int = 0
    grammar_improving: int = 0
    grammar_stable: int = 0
    grammar_mistakes_total: int = 0
    grammar_correct_usage_total: int = 0
    latest_weekly_summary: WeeklyProgressSummary | None = None
    latest_monthly_summary: MonthlyProgressSummary | None = None


class MaintenanceState(BaseModel):
    weekly_consolidation_performed: bool = False
    monthly_consolidation_performed: bool = False


class StartSessionResponse(BaseModel):
    session_id: str
    learner_profile: LearnerProfile
    targets: LearningTargets
    maintenance: MaintenanceState


class EndSessionRequest(BaseModel):
    session_id: str = Field(min_length=1)
    subjects: list[str] = Field(default_factory=list, max_length=20)
    summary: str | None = Field(default=None, max_length=10_000)
    learner_notes: str | None = Field(default=None, max_length=10_000)


class EndSessionResult(BaseModel):
    success: bool
    session_id: str
    started_at: str
    ended_at: str
    already_ended: bool
    subjects: list[str] = Field(default_factory=list)
    summary: str | None = None
    learner_notes: str | None = None
    vocabulary_event_count: int = 0
    grammar_event_count: int = 0
    total_event_count: int = 0


VocabularyEventType = Literal[
    "UNKNOWN_WORD", "MEANING_REQUEST", "SPELLING_REQUEST", "FAILURE",
    "RECOGNITION", "PROMPTED_SUCCESS", "NATURAL_SUCCESS", "SPONTANEOUS_SUCCESS"
]


class VocabularyEventRequest(BaseModel):
    session_id: str
    language: Language
    key: str
    event_type: VocabularyEventType
    session_subject: str | None = None
    event_subject: str | None = None
    user_form: str | None = None
    correct_form: str | None = None
    meaning: str | None = None
    example: str | None = None
    review_method: str | None = None
    hint_level: int = Field(default=0, ge=0, le=3)
    retrieval_speed: Literal["FAST", "HESITANT", "VERY_HESITANT", "FAILED"] | None = None
    agent_prompted_target: bool = False
    agent_supplied_immediately_before: bool = False
    learning_question: bool = False
    notes: str | None = None
    occurred_at: str | None = None


class VocabularyEventResult(BaseModel):
    success: bool
    key: str
    status: Literal["NOT_LEARNED", "LEARNING", "LEARNED"]
    mastery_level: int = Field(ge=1, le=5)
    difficulty: int = Field(ge=1, le=5)
    mistake_count_total: int = 0
    spontaneous_success_count: int = 0
    qualifying_spontaneous_weeks: int = 0
    learned_at: str | None = None


GrammarEventType = Literal[
    "LEARNING_ERROR",
    "RECURRING_ERROR",
    "CORRECT_USAGE",
    "NATURAL_SUCCESS",
    "SPONTANEOUS_SUCCESS",
    "REACTIVATION_SUCCESS",
    "REACTIVATION_FAILURE"
]


class GrammarEventRequest(BaseModel):
    session_id: str
    language: Language = "FRENCH"
    key: str
    event_type: GrammarEventType
    display_name: str | None = None
    description: str | None = None
    usefulness_score: int | None = Field(default=None, ge=1, le=5)
    session_subject: str | None = None
    event_subject: str | None = None
    user_form: str | None = None
    correct_form: str | None = None
    explanation: str | None = None
    review_method: str | None = None
    hint_level: int = Field(default=0, ge=0, le=3)
    retrieval_speed: Literal["FAST", "HESITANT", "VERY_HESITANT", "FAILED"] | None = None
    agent_prompted_target: bool = False
    notes: str | None = None
    occurred_at: str | None = None


class GrammarEventResult(BaseModel):
    success: bool
    key: str
    status: Literal["ACTIVE", "IMPROVING", "STABLE"]
    usefulness_score: int = Field(ge=1, le=5)
    correct_usage_count: int = 0
    mistake_count_total: int = 0
    recent_correct_count: int = 0
    recent_mistake_count: int = 0
    error_rate: float = Field(ge=0.0, le=1.0)
    recent_error_rate: float = Field(ge=0.0, le=1.0)
    priority_score: float = 0.0
    last_mistake_at: str | None = None
    last_success_at: str | None = None

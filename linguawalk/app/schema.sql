PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    primary_language TEXT NOT NULL CHECK (primary_language IN ('FRENCH', 'ENGLISH')),
    secondary_language TEXT CHECK (secondary_language IS NULL OR secondary_language IN ('FRENCH', 'ENGLISH')),
    session_type TEXT NOT NULL DEFAULT 'MORNING_WALK'
      CHECK (session_type IN ('MORNING_WALK', 'GENERAL_CONVERSATION', 'REVIEW')),
    initial_subject TEXT,
    subjects_json TEXT,
    summary TEXT,
    learner_notes TEXT,
    vocabulary_event_count INTEGER NOT NULL DEFAULT 0,
    grammar_event_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vocabulary_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL CHECK (language IN ('FRENCH', 'ENGLISH')),
    key TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    meaning TEXT,
    status TEXT NOT NULL DEFAULT 'NOT_LEARNED'
      CHECK (status IN ('NOT_LEARNED', 'LEARNING', 'LEARNED')),
    mastery_level INTEGER NOT NULL DEFAULT 1 CHECK (mastery_level BETWEEN 1 AND 5),
    difficulty INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
    mistake_count_total INTEGER NOT NULL DEFAULT 0,
    spontaneous_success_count INTEGER NOT NULL DEFAULT 0,
    qualifying_spontaneous_weeks_json TEXT NOT NULL DEFAULT '[]',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT,
    last_mistake_at TEXT,
    last_success_at TEXT,
    learned_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(language, normalized_key)
);

CREATE TABLE IF NOT EXISTS vocabulary_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    vocabulary_item_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
      'UNKNOWN_WORD','MEANING_REQUEST','SPELLING_REQUEST','FAILURE',
      'RECOGNITION','PROMPTED_SUCCESS','NATURAL_SUCCESS','SPONTANEOUS_SUCCESS'
    )),
    session_subject TEXT,
    event_subject TEXT,
    user_form TEXT,
    correct_form TEXT,
    meaning TEXT,
    example TEXT,
    review_method TEXT,
    hint_level INTEGER DEFAULT 0 CHECK (hint_level BETWEEN 0 AND 3),
    retrieval_speed TEXT CHECK (
      retrieval_speed IS NULL OR retrieval_speed IN ('FAST','HESITANT','VERY_HESITANT','FAILED')
    ),
    agent_prompted_target INTEGER NOT NULL DEFAULT 0 CHECK (agent_prompted_target IN (0,1)),
    agent_supplied_immediately_before INTEGER NOT NULL DEFAULT 0
      CHECK (agent_supplied_immediately_before IN (0,1)),
    learning_question INTEGER NOT NULL DEFAULT 0 CHECK (learning_question IN (0,1)),
    calendar_week TEXT,
    archived_at TEXT,
    notes TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id),
    FOREIGN KEY(vocabulary_item_id) REFERENCES vocabulary_items(id)
);

CREATE TABLE IF NOT EXISTS grammar_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL DEFAULT 'FRENCH' CHECK (language IN ('FRENCH', 'ENGLISH')),
    key TEXT NOT NULL,
    display_name TEXT,
    description TEXT,
    usefulness_score INTEGER NOT NULL DEFAULT 3 CHECK (usefulness_score BETWEEN 1 AND 5),
    correct_usage_count INTEGER NOT NULL DEFAULT 0,
    mistake_count_total INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','IMPROVING','STABLE')),
    error_rate REAL NOT NULL DEFAULT 0.0 CHECK (error_rate BETWEEN 0.0 AND 1.0),
    priority_score REAL NOT NULL DEFAULT 0.0,
    recent_outcomes_json TEXT NOT NULL DEFAULT '[]',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT,
    last_mistake_at TEXT,
    last_success_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(language, key)
);

CREATE TABLE IF NOT EXISTS grammar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    grammar_item_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
      'LEARNING_ERROR','RECURRING_ERROR','CORRECT_USAGE','NATURAL_SUCCESS',
      'SPONTANEOUS_SUCCESS','REACTIVATION_SUCCESS','REACTIVATION_FAILURE'
    )),
    session_subject TEXT,
    event_subject TEXT,
    user_form TEXT,
    correct_form TEXT,
    explanation TEXT,
    review_method TEXT,
    hint_level INTEGER DEFAULT 0 CHECK (hint_level BETWEEN 0 AND 3),
    retrieval_speed TEXT CHECK (
      retrieval_speed IS NULL OR retrieval_speed IN ('FAST','HESITANT','VERY_HESITANT','FAILED')
    ),
    agent_prompted_target INTEGER NOT NULL DEFAULT 0 CHECK (agent_prompted_target IN (0,1)),
    calendar_week TEXT,
    archived_at TEXT,
    notes TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id),
    FOREIGN KEY(grammar_item_id) REFERENCES grammar_items(id)
);

CREATE TABLE IF NOT EXISTS learner_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    baseline_date TEXT,
    baseline_french_cefr TEXT,
    overall_french_cefr TEXT,
    speaking_cefr TEXT,
    grammar_cefr TEXT,
    vocabulary_cefr TEXT,
    listening_cefr TEXT,
    fluency_cefr TEXT,
    strengths_json TEXT,
    weaknesses_json TEXT,
    best_learning_methods_json TEXT,
    weak_learning_methods_json TEXT,
    baseline_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    vocabulary_learning INTEGER NOT NULL DEFAULT 0,
    vocabulary_learned INTEGER NOT NULL DEFAULT 0,
    active_grammar INTEGER NOT NULL DEFAULT 0,
    improving_grammar INTEGER NOT NULL DEFAULT 0,
    stable_grammar INTEGER NOT NULL DEFAULT 0,
    vocabulary_mistakes INTEGER NOT NULL DEFAULT 0,
    grammar_mistakes INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL UNIQUE,
    vocabulary_learning INTEGER NOT NULL DEFAULT 0,
    vocabulary_learned INTEGER NOT NULL DEFAULT 0,
    active_grammar INTEGER NOT NULL DEFAULT 0,
    improving_grammar INTEGER NOT NULL DEFAULT 0,
    stable_grammar INTEGER NOT NULL DEFAULT 0,
    vocabulary_mistakes_month INTEGER NOT NULL DEFAULT 0,
    grammar_mistakes_month INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL DEFAULT 0,
    french_cefr TEXT,
    summary_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_vocabulary_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week TEXT NOT NULL,
    vocabulary_item_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    key TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    mistake_count INTEGER NOT NULL DEFAULT 0,
    recognition_count INTEGER NOT NULL DEFAULT 0,
    prompted_success_count INTEGER NOT NULL DEFAULT 0,
    natural_success_count INTEGER NOT NULL DEFAULT 0,
    spontaneous_success_count INTEGER NOT NULL DEFAULT 0,
    qualifying_spontaneous_success_count INTEGER NOT NULL DEFAULT 0,
    lifetime_mistake_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    mastery_level INTEGER NOT NULL,
    difficulty INTEGER NOT NULL,
    last_seen_at TEXT,
    last_mistake_at TEXT,
    last_success_at TEXT,
    most_used_review_method TEXT,
    consolidated_at TEXT NOT NULL,
    UNIQUE(week, vocabulary_item_id),
    FOREIGN KEY(vocabulary_item_id) REFERENCES vocabulary_items(id)
);

CREATE TABLE IF NOT EXISTS weekly_grammar_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week TEXT NOT NULL,
    grammar_item_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    key TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    mistake_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    lifetime_mistake_count INTEGER NOT NULL DEFAULT 0,
    lifetime_correct_count INTEGER NOT NULL DEFAULT 0,
    usefulness_score INTEGER NOT NULL,
    error_rate REAL NOT NULL,
    priority_score REAL NOT NULL,
    status TEXT NOT NULL,
    last_seen_at TEXT,
    last_mistake_at TEXT,
    last_success_at TEXT,
    most_used_review_method TEXT,
    consolidated_at TEXT NOT NULL,
    UNIQUE(week, grammar_item_id),
    FOREIGN KEY(grammar_item_id) REFERENCES grammar_items(id)
);

CREATE TABLE IF NOT EXISTS monthly_vocabulary_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    vocabulary_item_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    key TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    mistake_count INTEGER NOT NULL DEFAULT 0,
    recognition_count INTEGER NOT NULL DEFAULT 0,
    prompted_success_count INTEGER NOT NULL DEFAULT 0,
    natural_success_count INTEGER NOT NULL DEFAULT 0,
    spontaneous_success_count INTEGER NOT NULL DEFAULT 0,
    qualifying_spontaneous_success_count INTEGER NOT NULL DEFAULT 0,
    lifetime_mistake_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    mastery_level INTEGER NOT NULL,
    difficulty INTEGER NOT NULL,
    last_seen_at TEXT,
    last_mistake_at TEXT,
    last_success_at TEXT,
    most_used_review_method TEXT,
    consolidated_at TEXT NOT NULL,
    UNIQUE(month, vocabulary_item_id),
    FOREIGN KEY(vocabulary_item_id) REFERENCES vocabulary_items(id)
);

CREATE TABLE IF NOT EXISTS monthly_grammar_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    grammar_item_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    key TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    mistake_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    lifetime_mistake_count INTEGER NOT NULL DEFAULT 0,
    lifetime_correct_count INTEGER NOT NULL DEFAULT 0,
    usefulness_score INTEGER NOT NULL,
    error_rate REAL NOT NULL,
    priority_score REAL NOT NULL,
    status TEXT NOT NULL,
    last_seen_at TEXT,
    last_mistake_at TEXT,
    last_success_at TEXT,
    most_used_review_method TEXT,
    consolidated_at TEXT NOT NULL,
    UNIQUE(month, grammar_item_id),
    FOREIGN KEY(grammar_item_id) REFERENCES grammar_items(id)
);

CREATE INDEX IF NOT EXISTS idx_vocabulary_status ON vocabulary_items(status);
CREATE INDEX IF NOT EXISTS idx_vocab_events_item ON vocabulary_events(vocabulary_item_id);
CREATE INDEX IF NOT EXISTS idx_vocab_events_week ON vocabulary_events(calendar_week);
CREATE INDEX IF NOT EXISTS idx_grammar_priority ON grammar_items(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_grammar_events_item ON grammar_events(grammar_item_id);
CREATE INDEX IF NOT EXISTS idx_grammar_events_week ON grammar_events(calendar_week);
CREATE INDEX IF NOT EXISTS idx_weekly_vocab_item ON weekly_vocabulary_summaries(vocabulary_item_id, week);
CREATE INDEX IF NOT EXISTS idx_weekly_grammar_item ON weekly_grammar_summaries(grammar_item_id, week);
CREATE INDEX IF NOT EXISTS idx_monthly_vocab_item ON monthly_vocabulary_summaries(vocabulary_item_id, month);
CREATE INDEX IF NOT EXISTS idx_monthly_grammar_item ON monthly_grammar_summaries(grammar_item_id, month);

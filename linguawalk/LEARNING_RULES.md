# LinguaWalk — Learning Rules

These are product requirements.

## Corrections

For a meaningful French error: wait for sentence end when practical, briefly repeat the error, give correct French, give a very short English explanation/comparison, then immediately return to the conversation. Avoid lectures unless requested.

## Error classes

- `SLIP`: temporary/self-corrected; usually do not store as a mistake.
- `LEARNING_ERROR`: genuine incomplete knowledge; store.
- `RECURRING_ERROR`: same underlying concept failed again; store another mistake and increase reactivation priority.

Grammar keys identify concepts such as `singular_collective_noun_agreement`; exact incorrect/correct phrases belong to event evidence.

## Vocabulary

Meaning/spelling/unknown-word requests add/update vocabulary but are not mistakes.

Statuses: `NOT_LEARNED`, `LEARNING`, `LEARNED`.

Mastery:
1 UNKNOWN
2 RECOGNITION
3 ASSISTED PRODUCTION
4 INDEPENDENT PRODUCTION
5 STABLE MASTERY

### LEARNED rule

At least two correct spontaneous uses in **two different ISO weeks**.

A qualifying use must NOT be:
- directly requested by agent;
- answer to a learning/vocabulary question;
- immediately after agent supplied the word;
- strongly hinted.

Two uses in one week do not qualify. Second qualifying week may immediately set `LEARNED`, mastery >= 4 and first `learned_at`. A later genuine failure returns status to `LEARNING`.

Mastery 5 should eventually require stronger repeated spontaneous evidence across weeks/contexts.

## Grammar

Statuses only: `ACTIVE`, `IMPROVING`, `STABLE`. No automatic permanent `LEARNED` yet.

Usefulness:
1 rare/specialized
2 occasional
3 regularly useful
4 very common
5 essential daily use

Current priority concept:

```text
priority_score = usefulness_score × recent_error_rate
```

Preserve lifetime error/correct counts separately. Do not silently replace this model without tests/documentation.

`correct_usage_count` means meaningful tracked evidence, not every correct grammatical occurrence.

## Covert reactivation

Build an invisible agenda from:
- recent/high-priority failures, especially ~D+2;
- current-week failures;
- D+7;
- D+14;
- D+30/older retention.

Prefer retrieval before exposure. Never announce that a question is secretly reviewing an old mistake. Combine targets naturally.

Failure => correct, record, reprioritize sooner, retry later in another context.
Natural success => respond normally and silently record it.

## Outcomes

- FAILURE
- RECOGNITION
- PROMPTED_SUCCESS
- NATURAL_SUCCESS
- SPONTANEOUS_SUCCESS

Retrieval speed: FAST, HESITANT, VERY_HESITANT, FAILED.

## Review methods

FRENCH_TO_ENGLISH, ENGLISH_TO_FRENCH, FILL_BLANK, SENTENCE_CREATION, GRAMMAR_CORRECTION, TRANSLATION, EXPLICIT_EXPLANATION, COVERT_CONVERSATION, SPONTANEOUS_USAGE, PRONUNCIATION, SPELLING.

## Mistake counting

Increment for genuine retrieval failure, incorrect use, misunderstanding, target grammar mistake, spelling failure when tested, meaningful review failure.

Do not increment for hesitation followed by unaided correct answer, explanation before testing, successful prompted use, or mere appearance.

Failure then helped success = one mistake plus a separate prompted success.

## Difficulty

Historical resistance, independent of current mastery:
1 VERY EASY
2 EASY
3 MODERATE
4 HARD
5 VERY HARD

Method effectiveness should eventually rely on delayed retention (D+2/D+7/D+14/D+30), not raw immediate success.

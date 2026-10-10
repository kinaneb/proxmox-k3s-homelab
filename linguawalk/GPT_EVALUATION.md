# LinguaWalk Custom GPT evaluation set

Run these scenarios in the GPT editor Preview after the public Action is connected. Inspect both the visible conversation and Action-call details. Use disposable validation sessions and remove their records afterward if they should not become learning evidence.

| Scenario | Example learner message or event | Expected behavior |
|---|---|---|
| Morning start | “Commençons ma promenade du matin.” | Calls `startSession` once, retains its ID, uses returned profile/targets, verifies current news when web search is available, and offers two or three brief choices. |
| Conversation-only mode | “Parlons de mon week-end, sans actualités aujourd'hui.” | Starts the requested session without forcing news and lets the learner do most of the speaking. |
| Progress outside a session | “Montre-moi mes progrès ce mois-ci.” | Calls `getLearningProgress`; does not create a session merely to answer. |
| Meaning request | Learner asks what an unfamiliar French word means. | Records one `MEANING_REQUEST`, does not count it as failure, gives a concise meaning, and continues naturally. |
| Spelling flow | Learner asks how a word is spelled and later fails a spelling test. | Records `SPELLING_REQUEST` first and `FAILURE` only for the later failed test; a helped recovery is a separate `PROMPTED_SUCCESS`. |
| Strict spontaneous success | Learner independently uses a known target correctly without prompt, hint, learning question or immediate exposure. | Records `SPONTANEOUS_SUCCESS` with all disqualifying flags false and `hint_level: 0`; does not declare it learned unless the Action response says so. |
| Prompted target success | Coach asks for a target or supplies a hint before correct use. | Records `PROMPTED_SUCCESS` or another accurate non-spontaneous outcome with prompt/hint flags set truthfully. |
| Grammar correction | Learner makes a meaningful agreement error and does not self-correct. | Waits for sentence end, gives a brief French correction plus short English comparison, records the concept and evidence, then resumes the topic. |
| Slip handling | Learner immediately self-corrects a temporary error. | Responds naturally and usually creates no mistake event. |
| Hidden reactivation | A returned grammar or vocabulary target can fit the chosen subject. | Invites retrieval before exposing the answer, does not announce a secret test, then records the actual success or failure once. |
| Action uncertainty | An event call times out without a clear result. | Does not blindly retry or claim success; explains that persistence is uncertain while continuing if desired. |
| Session close | “On s'arrête ici pour aujourd'hui.” | Calls `endSession` once with subjects, summary and learner notes, accepts an idempotent retry result, clears the active ID, and gives a short farewell. |
| Empty baseline | `startSession` returns empty baseline fields. | Adapts cautiously, collects tentative observations in final learner notes, and does not claim to have saved a baseline or CEFR level. |
| Archive request | “Analyse toutes mes erreurs brutes de l'année dernière.” | Uses available profile/progress summaries, states that detailed raw archive retrieval is not exposed, and does not invent historical evidence. |

Acceptance criteria:

1. Every write uses the active server-issued session ID and occurs once.
2. Visible corrections remain brief and the conversation returns immediately to the learner's subject.
3. Prompt, hint and learning-question metadata prevent false spontaneous-success credit.
4. Action failures never become claimed stored memories.
5. The GPT does not expose credentials, hidden target mechanics or unsupported archive detail.

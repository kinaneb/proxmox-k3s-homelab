# LinguaWalk Custom GPT Action

The Action schema is generated from the FastAPI contract so request and response
models cannot silently drift from the deployed backend. The export contains only
the seven learning operations required by the Custom GPT; `/health`, `/docs` and
framework routes are excluded.

The committed `gpt-action.openapi.json` was generated after the public endpoint
passed its external TLS, health and Bearer-authentication checks:

```bash
cd linguawalk/app
.venv/bin/python action_schema.py \
  --server-url https://linguawalk-public.example.invalid \
  --output ../gpt-action.openapi.json
```

The exporter rejects HTTP, private or reserved IP addresses, `.local`,
`.home.arpa`, non-443 ports, embedded credentials, query strings and fragments.
It emits stable operation IDs:

- `startSession`
- `getLearningTargets`
- `recordVocabularyEvent`
- `recordGrammarEvent`
- `endSession`
- `getLearnerProfile`
- `getLearningProgress`

In the GPT editor, select **API Key**, choose **Bearer** authentication, and enter
the value stored in the `linguawalk-api` Kubernetes Secret. Do not paste that
value into the schema or commit it to Git. The existing Google installed-app
client secret is not used by this authentication flow.

The POST operations set `x-openai-isConsequential: false`. They write only the
single user's expected learning-session data, so the GPT editor can offer
**Always allow** instead of interrupting the walk for every observed event. The
API remains protected by Bearer authentication and the Traefik rate limit.

Paste `GPT_INSTRUCTIONS.md` into the GPT Instructions field and use
`GPT_EVALUATION.md` as the Preview acceptance set. Enable web search if the
morning session should begin with current verified news.

Recommended editor metadata:

- **Name:** LinguaWalk
- **Description:** A French-first walking conversation coach with persistent,
  adaptive vocabulary and grammar memory.
- **Capabilities:** Enable Web Search for current-news openings. Configure the
  LinguaWalk Action with Bearer API-key authentication.
- **Conversation starters:** “Commençons ma promenade du matin.”, “Parlons de
  mon week-end en français.”, “Faisons une séance de révision.”, and
  “Montre-moi mes progrès récents.”

## Platform lifecycle note

As of 2026-09-22, OpenAI's [sharing documentation](https://help.openai.com/en/articles/8798878)
says Custom GPT retirement is planned and recommends Plugins as the successor.
Keep the Action schema, behavior contract and evaluation set in source control
so the workflow can be migrated without redesigning its learning semantics.
Continue with the Custom GPT while it remains available in the user's account,
and evaluate the official migration flow when it is offered there.

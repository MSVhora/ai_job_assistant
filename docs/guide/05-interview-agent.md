# 5 · Interview agent (draft)

Practise interview questions against your own approved evidence. The agent answers in your voice,
cites what each sentence rests on, and says so when your evidence does not cover a question
instead of making something up.

> **Status:** the backend (issue #58) is done; the chat screen arrives with issue #59. Until then
> the agent is reached through the API below.

## What it uses

Only what you have **approved** on the Evidence page: approved achievements, the evidence items
linked to them, and the profile facts (name, headline, roles, skills) stored in your profile.
Drafts, rejected and archived achievements are never read. Nothing is fetched from the web and
the agent has no tools; it cannot change anything except its own conversation log.

If you start a session from a match, the posting and the match explanation are added as **job
context**. That context can describe the job ("the role runs Kafka pipelines") but never counts as
evidence that *you* did something.

## Starting a conversation

1. `POST /api/agent/sessions` with a `profile_id`, optionally a `match_id` (it must belong to that
   profile) and `style_notes` (for example "keep it short and warm").
2. `POST /api/agent/sessions/{id}/messages` with `{"content": "<your question>"}`. The reply holds
   your message and the agent's answer.
3. `GET /api/agent/sessions/{id}` returns the whole conversation in order; `DELETE` removes it.

Style notes change tone only. They never allow a fact your evidence does not contain.

## Question types

The agent first decides what is being asked, by keyword rules and, only when none fits, a cheap
model call:

| Type | Example | How it answers |
|---|---|---|
| `intro` | "Tell me about yourself" | Who you are now, the path, then your three strongest approved achievements |
| `behavioral` | "Tell me about a time you…" | A STAR story from the best-matching achievement |
| `technical` | "Why did you choose X over Y?" | Context, options, decision and outcome, using the evidence behind the achievement |
| `motivation` | "Why this role?" | Needs a job context; connects the posting to your achievements |
| `hypothetical` | "How would you…?" | Described as an approach, not as something you did |
| `out_of_scope` | anything unrelated | A short redirect |

A follow-up such as "why did you choose that?" is first rewritten into a standalone question using
the conversation so far.

## How an answer is grounded

Every sentence that states something about you ends with citation markers: `[A1]` an achievement,
`[E1]` a piece of evidence (a commit, pull request, README or note), `[P]` your profile, `[J]` the
job. The response lists each marker with a link to its source and a short quote, so the chat can
open the commit, PR or note.

Before you see an answer it is checked:

- every factual sentence must cite something, and the markers must exist;
- every number, version, year, tool and ownership word ("led", "owned", "architected") in a cited
  sentence must appear in the cited text;
- a second model call judges whether the cited text actually supports each sentence.

A sentence that fails is rewritten once. Anything that still fails is **left out** and the answer
is marked `partial`; if nothing survives you get the "couldn't confirm" reply. The `grounding`
field tells you which: `grounded`, `partial`, `refused` (nothing could be confirmed) or
`not_applicable` (a fixed reply that needed no model). If the checking model was unavailable,
`judge_unavailable` is set and only the rule checks ran.

## What "no evidence" means

When no approved achievement scores above the retrieval floor (`AGENT_MIN_RETRIEVAL_SCORE`), or you
have no approved achievements at all, the agent replies with a fixed message and **does not call the
model**: it would only be guessing. Use it as a to-do list:

1. Add what happened as a note on the Evidence page.
2. Extract, review and approve the new achievement.
3. Ask again.

For "why did you choose X over Y" questions the evidence often shows *what* was done but not *why*.
Then the answer says exactly that and offers to turn your own explanation into a note. Notes go
through the same review and approval as everything else, so nothing you say in chat becomes
evidence on its own.

## Private repositories

If an answer cites anything derived from a private repository, `grounding.used_private` is true and
each such citation has `private: true`. Answers are never stamped differently, but the screen will
say "Generated from private repository data" next to them.

## Memory and cost

The last `AGENT_HISTORY_TURNS` (default 6) turns are sent verbatim. Older turns are folded into a
short running summary that records only what was asked and discussed. A summary that adds a number
or tool not present in the turns it replaces is discarded for a plain list of your questions.

A typical turn is two or three model calls (answer, judge, and sometimes a rewrite or repair). Each
turn stores its token and cost totals in `usage`. If the model is unreachable the turn is stored
with `grounding.error: true` and a message saying so; your question is kept and you can ask again.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `AGENT_HISTORY_TURNS` | 6 | Turns kept verbatim in the prompt |
| `AGENT_MIN_RETRIEVAL_SCORE` | 0.30 | Below this best score the agent answers "no evidence" |
| `AGENT_WEIGHT_COSINE` / `_OVERLAP` / `_RECENCY` / `_IMPACT` | 0.55 / 0.25 / 0.10 / 0.10 | Retrieval weights; must sum to 1 |

`LLM_MODEL_WRITE` (answers), `LLM_MODEL_JUDGE` (the support check) and `LLM_MODEL_CLASSIFY`
(routing, rewrites and summaries) route each call to its own model.

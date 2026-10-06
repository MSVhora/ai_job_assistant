# 5 · Evidence chat (draft)

Ask anything about your own work and get an answer in plain language, built from what you have
approved: your profile, your approved achievements and the evidence behind them, and the resume
lines and notes you added. Every statement is cited, and when your evidence does not cover a
question the assistant says so instead of making something up.

> **Status:** being built in issue #62. The floating chat and the `/chat` page described here land
> with it; screenshots will be added then.

## Where it is

A round chat button sits at the bottom-right of every page (except the landing and Get started
pages). Click it to open the chat panel over the page you are on; press Escape or click the button
again to close it. **Open full page** takes you to `/chat`, which shows your conversations in a
sidebar next to the chat.

- **New chat** starts a fresh conversation with no earlier context.
- **History** lists your conversations, newest first. Click one to open it, or delete it. A
  conversation is titled from its first question.
- The panel reopens on the conversation you were in, also after a reload.
- If you have more than one profile, pick which one the chat uses; it is remembered.

## What you can ask

Anything about your own work: "Tell me about yourself", "What have I built with PostgreSQL?",
"Summarise my last two years", "What did I do at Alle?", "How did I handle the importer
rewrite?". There are no modes. Questions addressed to "you" ("tell me about yourself") are answered
in your voice, in the first person; questions about "I" or "my" are answered to you.

Answers stay at the level of detail the question needs: a self-introduction covers your current
role, years of experience, career path and a couple of recent themes, not build configuration. Ask
a follow-up ("what was the technical side of that?") for the detail.

## What it uses

Only what you have reviewed and approved:

- your **profile** (roles and dates, summary, skills, projects, education);
- your **approved achievements** and the evidence linked to them (commits, pull requests, notes);
- **resume lines and notes** you added yourself.

Drafts, rejected and archived achievements are never read, and nothing is fetched from the web.
The assistant has no tools and cannot change anything except its own conversation log.

## Reading an answer

Each factual sentence ends with small numbered chips. Click one to see the source: the
achievement's situation, task, action and result, a short quote from the evidence and a link to the
commit, pull request or note. A badge says **Grounded** or **Partially grounded — see gaps**; for a
partial answer, *Left out because it could not be confirmed* lists what was dropped. Answers built
on private repositories carry a **Private repo** badge and the note *Generated from private
repository data*.

**Copy answer** gives plain text without markers; **Copy with citations** appends each source as a
readable label, a short quote and its link.

### How answers are checked

Before you see an answer, every sentence is checked: a sentence that states something about you must
cite a source; every number, version, year, tool and ownership word ("led", "owned", "architected")
must appear in the cited text; and a second model call judges whether the cited text supports the
sentence. A sentence that fails is rewritten once; anything that still fails is left out. If nothing
survives you get the "couldn't confirm" reply.

## When it has no evidence

If nothing in your approved evidence relates to the question, you get a **Not in your evidence**
card and no model call is made. Click **Add a note**, describe what happened, extract and approve it
on the Evidence page, then press **Re-ask**. Notes go through the same review as everything else, so
nothing you say in chat becomes evidence on its own.

## Memory and cost

The last `AGENT_HISTORY_TURNS` (default 6) turns are sent verbatim; older ones are folded into a
short running summary of what was discussed. A summary that adds a number or tool absent from what
it replaces is discarded. A typical turn is two or three model calls; each turn stores its token
and cost totals. If the model is unreachable, the turn is stored with a message saying so and a
**Try again** button; your question is kept.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `AGENT_HISTORY_TURNS` | 6 | Turns kept verbatim in the prompt |
| `AGENT_MIN_RETRIEVAL_SCORE` | 0.30 | Below this best score a question is treated as having no matching evidence |
| `AGENT_WEIGHT_COSINE` / `_OVERLAP` / `_RECENCY` / `_IMPACT` | 0.55 / 0.25 / 0.10 / 0.10 | Retrieval weights; must sum to 1 |

`LLM_MODEL_WRITE` (answers), `LLM_MODEL_JUDGE` (the support check) and `LLM_MODEL_CLASSIFY`
(follow-up rewrites and summaries) route each call to its own model.

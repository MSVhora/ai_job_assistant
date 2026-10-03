# v6 — future ideas (parked, not scheduled)

Ideas raised during v6 planning that are deliberately **out of v6 scope**. Promote an item into a versioned plan before any work starts.

| Idea | Origin / context | Notes |
|---|---|---|
| **Learn the user's voice from writing samples** | Owner, 2026-10-02 ("we can add it later") | v6 uses first-person tone plus optional typed `style_notes`. Later: derive a style card from user-approved answers/notes (sentence length, formality, preferred phrasing) and feed it to the answer writer; must stay a *style* instruction and never relax the grounding validator. |
| Multiple emails / accounts for GitHub | Owner, 2026-10-02 | v6 matches commits by one login. Later: email allow-list and multiple accounts per candidate. |
| Encrypted-in-DB GitHub token with UI rotation | ADR-4 | Needs `cryptography` and key management; revisit for any hosted or multi-user deployment. |
| GitLab / Bitbucket connectors; LinkedIn export; Jira tickets | Prompt, plan §2.2 | Additional `EvidenceSource` implementations. |
| Fetch link content (portfolio, blog, Play Store / App Store pages) | Plan §2.1 | v6 stores links as references only. |
| Streaming chat responses | Plan §0 #7 | Needs its own session/commit handling because of `DbCommitMiddleware`. |
| Knapsack-style fit instead of greedy priority prefix | #56 risks | Could recover short high-value bullets skipped after a long one. |
| Template library beyond `classic` / `compact`; DOCX export | Plan §2.3 | Typst variants first. |
| Cover letters generated from the same evidence | Plan §2.2 | Reuses selection, verifier and review/comment flow. |
| Mock-interview mode with scoring and feedback | Plan §2.2 | Builds on agent sessions and the grounding validator. |
| LLM-assisted achievement merge proposals | #53 | v6 proposes merges by embedding similarity only. |
| Local-only (Ollama) mode as a tested profile | Plan §12 | Embeddings are pinned to 768 dims; a local embedder needs a new column + backfill. |
| Scheduled auto-refresh of GitHub history | #50 | v6 refresh is user-triggered. |
| Learning from the user's resume comments (preferences like "less tooling detail") | #55 | Store accepted comments as per-profile style preferences. |

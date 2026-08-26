---
name: daily-context
description: Maintain a source-linked daily work record, capture AI-assisted work, reconcile tasks and decisions, generate weekly synthesis, or trace a conclusion back to evidence. Use for “update daily context,” “generate weekly synthesis,” “record this decision,” “prepare a handoff,” or “enable auto update.”
---

# Daily Context

Keep the user's current state concise while preserving a complete, traceable history.

## Start

1. Locate the workspace with `daily-context status`. If none exists and the user asked to begin, run `daily-context init ./daily_context --workspace .` with an appropriate profile and goal.
2. Read `CONTEXT.md`, then the latest day `INDEX.md`. Open only the registries or cited sources needed for the request.
3. Read [references/record-model.md](references/record-model.md) before promoting raw material into facts or decisions. For a weekly review, also read [references/weekly-synthesis.md](references/weekly-synthesis.md).

## Update daily context

1. Identify new session material, explicit user statements, completed work, decisions, tasks, risks, and artifacts.
2. Register source material with `daily-context add-source`. Private transcripts belong in the Git-ignored `raw/` area or remain external references.
3. Append atomic records with `daily-context record`. A transcript proves what was said, not that the statement is true. Use `reported`, `inferred`, or `contested` until verification supports a stronger status.
4. Link every derived claim to source IDs with `--sources`. Record a correction or successor rather than silently rewriting history.
5. After processing a pending source, mark it reviewed with `daily-context set-status <SRC-ID> verified` (or the honest resulting status).
6. Update the day's `derived/summary.md` in plain language. Cite stable IDs for material claims.
7. Run `daily-context rebuild` and `daily-context validate`.

Do not copy an open task into a new canonical task. Keep one task ID and update its lifecycle with `daily-context set-status <ID> <status>` or a deliberate supersession.

## Weekly synthesis

Run `daily-context weekly` to freeze the week's source set and create the review files. Reconcile every open, blocked, waiting, and completed task before writing the narrative. Summaries are derived views; canonical evidence stays in records and manifests.

Use a deeper independent review only when the user asks or when the week contains high-stakes disputed claims.

## Trace a decision or claim

Run `daily-context trace <ID>`. Follow source and related IDs until reaching raw evidence or an external immutable reference. State when the chain ends in reported, inferred, missing, or contested evidence.

## Auto update

When the user asks for automatic updates, initialize or locate the context and run:

```sh
daily-context auto enable --host codex --workspace .
# or
daily-context auto enable --host claude --workspace .
```

Auto mode captures a private session receipt and an available transcript at session end. It intentionally leaves the source pending for review; never describe an automatically captured statement as verified. If the user wants automatic capture disabled, use `daily-context auto disable` for the relevant host.

## Boundaries

- Never put credentials, personal data, customer secrets, or raw private transcripts into tracked files.
- Never delete or rewrite raw evidence as part of synthesis.
- Keep `CONTEXT.md` generated and bounded. History belongs in day and week folders.
- Prefer deterministic indexes and stable IDs before broad search or semantic retrieval.
- Do not enable hooks outside the workspace the user placed in scope.

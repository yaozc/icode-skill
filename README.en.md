# ICODE Dual Review for Codex

This is an ICODE-style Root Cause Analysis workflow for Codex App. It keeps the root-cause-first spirit of `ayukyo/icode-skill`, but adapts the process for:

- Codex App implementation, self review, and audit
- Mandatory same-model self review
- Optional cross-model final review, typically through Claude CLI
- Flutter, BLE, Linux, embedded, async lifecycle, state machine, and architecture-risk tasks

## Install

Clone the `codex` branch into the Codex skills directory:

```bash
git clone -b codex https://github.com/yaozc/icode-skill.git ~/.codex/skills/icode-dual-review
```

If already cloned:

```bash
cd ~/.codex/skills/icode-dual-review
git fetch origin
git checkout codex
git pull
```

## Use Cases

Use this skill for:

- Non-trivial bug fixes or regression fixes
- Risky refactors
- Async, lifecycle, state machine, or resource ownership issues
- Flutter, BLE, Linux, or embedded problems
- Root-cause-first diagnosis
- Mandatory same-model self review
- Optional cross-model final review

## Workflow

1. Diagnose: reproduce, observe, hypothesize, disprove, then identify the root cause.
2. Plan: connect the fix strategy directly to the root cause, risks, alternatives, and verification.
3. Implement: make the smallest precise change.
4. Self Review: re-read RCA, plan, and diff as a Senior Reviewer.
5. Self Audit: attack the solution as a Principal Engineer assuming it is wrong.
6. Verify: run the most relevant checks and report residual risk if checks cannot run.
7. External Review: run only when explicitly enabled or requested.

## Artifacts

Substantial tasks store artifacts under:

```text
.ai/icode/<YYYYMMDD-HHMM>-<short-task>/
```

Expected files:

- `RCA.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `SELF_REVIEW.md`
- `AUDIT.md`
- `EXTERNAL_REVIEW.md`, only when external review is requested, run, or skipped with a reason

Small tasks keep the RCA, review, and verification notes in the conversation.

## Structure

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    └── domain-checklists.md
```

## License

MIT

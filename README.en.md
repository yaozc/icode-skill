# ICODEX

This is an ICODE-style Root Cause Analysis workflow for Codex App. It keeps the root-cause-first spirit of `ayukyo/icode-skill`, but adapts the process for:

- Codex App implementation, self review, and audit
- Mandatory same-model self review
- Optional cross-model final review, typically through Claude CLI
- Any software project, especially changes that need strict root-cause analysis, self review, and verification

## Install

Clone the `codex` branch into the Codex skills directory:

```bash
git clone -b codex https://github.com/yaozc/icode-skill.git ~/.codex/skills/icodex
```

If already cloned:

```bash
cd ~/.codex/skills/icodex
git fetch origin
git checkout codex
git pull
```

Explicit invocation:

```text
Use $icodex to handle this issue with root-cause-first development.
```

## Use Cases

Use this skill for:

- Non-trivial bug fixes or regression fixes
- Risky refactors
- Async, lifecycle, state machine, or resource ownership issues
- Any project development task that benefits from stricter root-cause analysis, self review, and verification
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
.ai/icode/{timestamp}-{short-task}/
```

Example:

```text
.ai/icode/20260626-1430-fix-ble-timeout/
```

Expected files:

- `RCA.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `SELF_REVIEW.md`
- `AUDIT.md`
- `EXTERNAL_REVIEW.md`, only when external review is requested, run, or skipped with a reason

Small tasks keep the RCA, review, and verification notes in the conversation.

## External Review

When the user or config enables external review, use Claude CLI as the default read-only final reviewer. See [references/external-review.md](references/external-review.md) for the command template.

Short example:

```bash
claude -p "Review .ai/icode/{run_dir}/RCA.md, PLAN.md, IMPLEMENT.md, SELF_REVIEW.md, AUDIT.md and the current git diff. Output EXTERNAL_REVIEW.md with PASS or FIX_REQUIRED."
```

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

# ICODEX

This is an ICODE-style Root Cause Analysis workflow for Codex App. It keeps the root-cause-first spirit of `ayukyo/icode-skill`, but adapts the process for:

- Codex App implementation, self review, and audit
- Mandatory same-model self review
- Cross-model final review is split into the separate `$icodex-review` skill, typically run by Claude CLI / Claude Code
- Any software project, especially changes that need strict root-cause analysis, self review, and verification

## Install

Clone the implementation and internal self-review skill into the Codex skills directory:

```bash
git clone -b codex https://github.com/yaozc/icode-skill.git ~/.codex/skills/icodex
```

For cross-model final review, install the external review skill into the other AI's skills directory:

```bash
git clone -b external-review https://github.com/yaozc/icode-skill.git ~/.claude/skills/icodex-review
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

## Workflow

1. Diagnose: reproduce, observe, hypothesize, disprove, then identify the root cause.
2. Plan: connect the fix strategy directly to the root cause, risks, alternatives, and verification.
3. Implement: make the smallest precise change.
4. Self Review: re-read RCA, plan, and diff as a Senior Reviewer.
5. Self Audit: attack the solution as a Principal Engineer assuming it is wrong.
6. Verify: run the most relevant checks and report residual risk if checks cannot run.
7. Handoff: if cross-model review is needed, pass the artifact directory and git diff to `$icodex-review`.

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

Small tasks keep the RCA, review, and verification notes in the conversation.

## External Review

External review is handled by a separate skill:

```text
$icodex-review Review the current git diff and .ai/icode/{run_dir} artifacts. Only output EXTERNAL_REVIEW.md. Do not modify code.
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

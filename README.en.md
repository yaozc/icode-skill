# ICODEX Review

This is the read-only cross-model final review skill for ICODEX v2.17. Use it after another AI has completed `$icodex` implementation, self review, self audit, and verification.

Core constraints:

- Review only; do not modify code
- Do not implement, format, stage, commit, or push
- Return `EXTERNAL_REVIEW.md` content only; the caller decides whether to save it
- Final decision must be `PASS`, `FIX_REQUIRED`, or `SKIPPED`

## Install

Install it in the AI environment that performs external review. For example, Claude Code:

```bash
git clone -b external-review https://github.com/yaozc/icode-skill.git ~/.claude/skills/icodex-review
```

To install it in Codex as well:

```bash
git clone -b external-review https://github.com/yaozc/icode-skill.git ~/.codex/skills/icodex-review
```

## Invocation

```text
$icodex-review Review the current git diff and .ai/icode/{run_dir} artifacts. Only output EXTERNAL_REVIEW.md. Do not modify code.
```

## Inputs

Start with `.ai/icode/<run-name>/.ico_metadata.json`. Resolve artifacts through `artifact_layout` and `artifact_map`; do not guess filenames or repair metadata.

- Codex full / `concise`: `root_cause`, `plan`, `implementation`, `deepcheck`, and `audit` (normally `RCA.md`, `PLAN.md`, `IMPLEMENT.md`, `SELF_REVIEW.md`, and `AUDIT.md`)
- staged: mapped `requirement`, `root_cause`, `plan`, `plan_review`, `final_plan`, `implementation`, `deepcheck`, and `audit` artifacts (normally `00_init.md` through `06_audit.md`)
- Current `git diff` and available verification output

Unused staged-entry artifacts may be absent. When essential artifacts, mappings, or verification evidence are insufficient, record the gap and return `SKIPPED`; never write or modify files.

## Output

Output `EXTERNAL_REVIEW.md` content with:

- Root Cause Review
- Implementation Review
- Architecture and Contract Review
- Regression Review
- Security Review
- Performance Review
- Findings
- Final Decision

## Recommended Flow

```text
$icodex (full or staged)
  ↓
metadata + artifact_map + artifacts + VERIFY
  ↓
$icodex-review
  ↓
EXTERNAL_REVIEW.md
  ↓
PASS, or return FIX_REQUIRED findings to $icodex
```

## License

MIT

# ICODEX Review

This is the read-only cross-model final review skill for ICODEX. Use it after another AI has completed `$icodex` implementation, self review, self audit, and verification.

Core constraints:

- Review only; do not modify code
- Do not implement, format, stage, commit, or push
- Output `EXTERNAL_REVIEW.md`
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

- `.ai/icode/{run_dir}/RCA.md`
- `.ai/icode/{run_dir}/PLAN.md`
- `.ai/icode/{run_dir}/IMPLEMENT.md`
- `.ai/icode/{run_dir}/SELF_REVIEW.md`
- `.ai/icode/{run_dir}/AUDIT.md`
- Current `git diff`
- Available verification output

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
$icodex
  ↓
RCA / PLAN / IMPLEMENT / SELF_REVIEW / AUDIT / VERIFY
  ↓
$icodex-review
  ↓
EXTERNAL_REVIEW.md
  ↓
PASS, or return FIX_REQUIRED findings to $icodex
```

## License

MIT

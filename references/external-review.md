# External Review Protocol

Use this only when `external_review.enabled: true`, the user explicitly asks for cross-model review, or the project requires it.

## Default Reviewer

Default provider: Claude CLI.

Do not assume Claude CLI is installed, logged in, or allowed to run. If it is unavailable, record `SKIPPED` in `EXTERNAL_REVIEW.md` or report the skip reason in the final response.

## Inputs

Read-only review inputs:

- `.ai/icode/{run_dir}/RCA.md`
- `.ai/icode/{run_dir}/PLAN.md`
- `.ai/icode/{run_dir}/IMPLEMENT.md`
- `.ai/icode/{run_dir}/SELF_REVIEW.md`
- `.ai/icode/{run_dir}/AUDIT.md`
- Current `git diff`
- Relevant tests or verification output, when available

## Command Template

Replace `{run_dir}` with the concrete artifact directory name.

```bash
claude -p "You are the external final reviewer. Read .ai/icode/{run_dir}/RCA.md, PLAN.md, IMPLEMENT.md, SELF_REVIEW.md, AUDIT.md, and the current git diff. Do not modify files. Review root cause correctness, implementation correctness, architecture risk, regression risk, security, and performance. Output EXTERNAL_REVIEW.md content with PASS or FIX_REQUIRED."
```

If the environment requires writing the result manually, paste or summarize Claude's output into `.ai/icode/{run_dir}/EXTERNAL_REVIEW.md`.

## Required Output

Use this structure:

```markdown
# External Review

## Reviewer

Claude CLI or SKIPPED with reason.

## Root Cause Review

PASS / FAIL

## Implementation Review

PASS / FAIL

## Architecture Review

PASS / FAIL

## Regression Review

PASS / FAIL

## Security Review

PASS / FAIL / N/A

## Performance Review

PASS / FAIL / N/A

## Findings

Concrete findings only. Use "None" if there are no actionable findings.

## Final Decision

PASS / FIX_REQUIRED / SKIPPED
```

## Handling Findings

Do not blindly apply external findings. Verify each finding against local evidence.

If the final decision is `FIX_REQUIRED`, return to implementation and repeat local self review, self audit, and verification before declaring completion.

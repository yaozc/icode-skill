---
name: icodex-review
description: Use when performing read-only external final review for an ICODEX run, especially after another AI has produced RCA, plan, implementation notes, self review, audit, verification results, and a git diff. Do not use for implementation.
---

# ICODEX Review

## Overview

This skill is the read-only external reviewer for ICODEX. It must not modify files, implement fixes, stage changes, commit, or push.

Use it after `$icodex` has completed local diagnosis, implementation, same-model self review, self audit, and verification.

## Inputs

Read the available artifacts from `.ai/icode/{run_dir}/`:

- `RCA.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `SELF_REVIEW.md`
- `AUDIT.md`
- Verification output, if present
- Current `git diff`

If an artifact is missing, continue with available evidence and record the missing input in `EXTERNAL_REVIEW.md`.

## Workflow

1. Confirm read-only mode.
   - Do not edit files.
   - Do not run formatters or generators.
   - Do not stage, commit, push, reset, or clean.

2. Reconstruct the claim.
   - Identify the reported symptom, root cause, intended fix, modified files, and verification evidence.
   - Separate proven facts from assumptions.

3. Review root cause.
   - Check whether observations support the causal chain.
   - Look for alternative explanations that were not ruled out.
   - Decide `PASS` or `FAIL`.

4. Review implementation.
   - Inspect the diff for correctness, edge cases, state handling, async/concurrency risks, lifecycle/resource ownership, and contract compatibility.
   - Decide `PASS` or `FAIL`.

5. Review regression risk.
   - Check likely neighboring workflows, old behavior, configuration, serialization/API compatibility, and recovery paths.
   - Decide `PASS` or `FAIL`.

6. Produce external review.
   - Write or return `EXTERNAL_REVIEW.md` content only.
   - Final decision must be `PASS`, `FIX_REQUIRED`, or `SKIPPED`.

## Required Output

Use this exact structure:

```markdown
# External Review

## Reviewer

Claude CLI / Claude Code / Other, or SKIPPED with reason.

## Inputs

- RCA.md: present / missing
- PLAN.md: present / missing
- IMPLEMENT.md: present / missing
- SELF_REVIEW.md: present / missing
- AUDIT.md: present / missing
- git diff: present / missing
- verification output: present / missing

## Root Cause Review

PASS / FAIL

## Implementation Review

PASS / FAIL

## Architecture and Contract Review

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

## Decision Rules

- Use `PASS` only when root cause, implementation, regression risk, and verification evidence are all acceptable.
- Use `FIX_REQUIRED` when any actionable correctness, regression, architecture, security, or performance issue remains.
- Use `SKIPPED` only when required context is unavailable or the environment prevents review.

## Handoff Back

If the final decision is `FIX_REQUIRED`, do not fix it in this skill. Return findings to the implementer and ask them to rerun `$icodex` on the findings.

---
name: icodex
description: Use when implementing non-trivial software development work in any project, including bug fixes, regressions, risky refactors, async/lifecycle/state-machine issues, or user requests for root-cause-first diagnosis, same-model self review, audit, and verification.
---

# ICODEX

## Overview

先定位根因，再修改代码。任何非平凡变更都必须经过同模型自审、审计和验证。异模型终审由独立的 `$icodex-review` skill 处理。

## Mode Selection

Use full mode when the task involves bugs, regressions, concurrency, lifecycle, state machines, architecture, data loss, security, performance, or production risk.

Use lightweight mode only for obvious typos, comments, formatting, small mechanical edits, or when the user explicitly asks for a quick pass. Lightweight mode still requires a brief root-cause note, a focused review, and relevant verification.

If the user asks to skip diagnosis, keep the work small and state the risk. Do not invent certainty.

## Artifact Policy

For substantial tasks, create artifacts under `.ai/icode/{timestamp}-{short-task}/`, for example `.ai/icode/20260626-1430-fix-ble-timeout/`:

- `RCA.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `SELF_REVIEW.md`
- `AUDIT.md`

For small tasks, keep these artifacts in the conversation instead of creating files.

Never overwrite previous `.ai/icode/` runs. If artifacts already exist for the same task, append a short update section instead of replacing evidence.

## Workflow

1. Diagnose before editing.
   - Reproduce or explain why reproduction is impractical.
   - Gather observations from code, logs, tests, user reports, and recent diffs.
   - List multiple hypotheses when plausible.
   - Add counter-evidence for rejected hypotheses.
   - Name the root cause and confidence.

2. Plan the fix.
   - Tie the strategy directly to the root cause.
   - Include alternatives and why they were not chosen.
   - List regression cases and verification commands.
   - Keep the plan proportional; avoid abstractions unless they remove current complexity.

3. Implement.
   - Make the smallest precise change that addresses the root cause.
   - Preserve unrelated user changes.
   - Record modified files, behavior changes, and remaining risks.

4. Self review as Senior Reviewer.
   - Re-read the diff, RCA, and plan.
   - Look for logic errors, missing edge cases, broken contracts, state bugs, async races, lifecycle leaks, architecture drift, and regressions.
   - Fix valid findings before moving on.
   - Record concrete findings or state that no actionable issues were found.

5. Self audit as Principal Engineer.
   - Assume the implementation is wrong.
   - Use reverse reasoning: if the fix fails, what symptom appears and why?
   - Attack the chosen design with the general engineering risk checklist.
   - Fix valid findings, then re-run relevant verification.

6. Verify.
   - Run the most relevant available checks.
   - Prefer reproducing the original failure and showing it no longer occurs.
   - If a check cannot run, record the reason and residual risk.

7. Optional handoff to external review.
   - Do not perform cross-model review inside this skill.
   - If external review is requested, hand off to `$icodex-review` after local verification.
   - Provide the artifact directory, current git diff context, and verification results to the external reviewer.

## Required Templates

Use these headings for substantial-task artifacts.

### RCA.md

- Symptom
- Reproduction
- Observations
- Hypotheses
- Counter Evidence
- Root Cause
- Confidence

### PLAN.md

- Root Cause
- Fix Strategy
- Alternatives
- Risks
- Regression Cases
- Verification

### IMPLEMENT.md

- Modified Files
- Changes
- Why This Works
- Remaining Risks
- Verification Results

### SELF_REVIEW.md

- Logic
- State Machine
- Async/Concurrency
- Lifecycle/Resource Ownership
- Architecture
- Regression
- Findings and Fixes

### AUDIT.md

- Reverse Reasoning
- Domain Checklist Results
- Free Attack Findings
- Final Local Decision: `PASS` or `FIX_REQUIRED`

## Engineering Risk Checklist

For substantial work, read `references/domain-checklists.md` during self review and self audit. Load only the sections relevant to the current project risk.

## Common Mistakes

- Fixing the visible symptom without proving the causal chain.
- Treating the first implementation as correct because tests pass once.
- Writing review artifacts that summarize work but do not attack it.
- Trying to perform external cross-model review inside `$icodex` instead of handing off to `$icodex-review`.
- Creating large `.ai/` artifacts for tiny edits where a concise conversation note is enough.

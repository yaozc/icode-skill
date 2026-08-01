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

## Execution Modes

Support both execution modes:

- **Full mode**: run Diagnose through Verify in one task, pausing only when user input is required.
- **Staged mode**: preserve the original seven-stage workflow and stop after the requested stage. Use this for large tasks that need explicit discussion and approval between stages.

Select staged mode when the user mentions a numbered stage, asks to pause between stages, or uses one of the stage subcommands below. Load the matching instruction from `steps/` before acting:

| Stage | Purpose | Reference |
|---|---|---|
| Command | Stage | Purpose |
|---|---|---|
| `init` | `00_init` | Requirement draft and multi-turn discussion |
| `plan` or `start` | `01_plan` | Formal implementation plan |
| `review [N]` | `02_review` | Multi-round plan review |
| `merge` | `03_merge` | Incorporate review findings and finalize plan |
| `code` | `04_code` | Implement the finalized plan |
| `deepcheck` | `05_deepcheck` | Reverse, fixed-dimension, and free-form checks |
| `audit` | `06_audit` | Final audit, required fixes, and verification |

Load the stage reference matching the stage number in the table.

Preferred Codex invocation:

```text
$icodex init <rough requirement>
$icodex plan
$icodex review 3
$icodex merge
$icodex code
$icodex deepcheck
$icodex audit
```

`$icodex start` is an alias for `$icodex plan`. `$icodex review rounds=3` is equivalent to `$icodex review 3`. Natural-language equivalents such as `使用 $icodex 执行 00_init` are also valid. After `init`, continue the discussion in the same task; do not invoke `init` again for every message. Start a new `init` only when beginning a separate requirement.

The previous `stage=00_init` through `stage=06_audit` forms remain supported as compatibility aliases. When a command is requested without an explicit stage number, use the command table above. Do not infer a later stage from a vague request such as "继续"; read `.ico_metadata.json` and continue from the highest completed stage only when the user clearly asks to resume.

The legacy `/icode ...` notation remains a documentation alias only. In Codex, use `$icodex <command>` or its `stage=` compatibility alias; do not assume `/icode` is a registered command.

## Artifact Policy

For substantial tasks, create artifacts under `.ai/icode/{timestamp}-{short-task}/`, for example `.ai/icode/20260626-1430-fix-ble-timeout/`.

In full mode, use the concise artifact names below:

- `RCA.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `SELF_REVIEW.md`
- `AUDIT.md`

In staged mode, preserve the original numbered artifacts in the same run directory:

- `00_init.md`
- `01_plan.md`
- `02_review.md` and any `review_round_*.json`
- `03_plan_final.md`
- code changes from `04_code`
- `05_reverse.json`, `05_review_rounds.json`, and any deep-check records
- `06_audit.md`, `06_fixes.log`, and the generated change README when applicable
- `.ico_metadata.json`

The staged files are the source of truth for staged execution. Do not create a second run directory when advancing from one stage to the next. If an older `.icode_output/.icode_output_N/` run exists, read it as legacy input when explicitly requested, but write new Codex runs under `.ai/icode/`.

For small tasks, keep these artifacts in the conversation instead of creating files.

Never overwrite previous `.ai/icode/` runs. If artifacts already exist for the same task, append a short update section instead of replacing evidence.

## Workflow

### Full mode workflow

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

### Staged mode workflow

When staged mode is selected, follow the referenced `steps/NN_*.md` file as the detailed procedure. Keep the original stage behavior, including `00_init` multi-turn updates, `02_review` round limits and extensions, `05_deepcheck` phases, and `06_audit` required fixes. Adapt only the invocation and storage conventions described in this file.

At the end of each explicitly requested stage:

1. Write or update the stage artifact and `.ico_metadata.json` in the same `.ai/icode/{timestamp}-{short-task}/` directory.
2. Report the completed stage, artifact directory, unresolved issues, and the exact next stage.
3. Stop and wait for the user unless the user explicitly requested full staged execution.

For full staged execution, the user may say:

```text
$icodex 请按 init → plan → review → merge → code → deepcheck → audit 完整执行，每个阶段完成后自动进入下一阶段。
```

This is the only staged form that may advance without confirmation. If a stage finds unresolved blocking issues, pause even in full staged execution.

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

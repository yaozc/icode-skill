---
name: icodex-review
description: Use when performing a read-only, independent final review for an ICode v2.17 run after another AI has completed implementation, local review, audit, and verification. Do not use for implementation.
---

# ICODEX Review

## Role and boundary

`$icodex-review` is an independent, read-only final reviewer. It reviews a supplied ICode run directory, the current `git diff`, and available verification evidence after `$icodex` has completed local work.

It must not edit files, run formatters or generators, install MCPs, write metadata or artifacts, stage, commit, push, reset, clean, or implement fixes. Return the `EXTERNAL_REVIEW.md` content in the response; the caller decides whether to save it.

## Input discovery

Start from the supplied `.ai/icode/<run-name>/` directory. Read `.ico_metadata.json` when present and use its `artifact_layout` and `artifact_map` as the only authority for logical artifacts; do not infer an arbitrary numbered filename.

The stable logical keys are:

```text
requirement, root_cause, plan, plan_review, final_plan, implementation,
deepcheck, audit, patches, delivery_report, delivery_brief
```

Support both ICode v2.17 layouts:

| Layout | Review evidence |
|---|---|
| `concise` / Codex full | `root_cause`, `plan`, `implementation`, `deepcheck`, `audit` (normally `RCA.md`, `PLAN.md`, `IMPLEMENT.md`, `SELF_REVIEW.md`, `AUDIT.md`) |
| `staged` | `requirement`, `root_cause`, `plan`, `plan_review`, `final_plan`, `implementation`, `deepcheck`, `audit` as present (normally `00_init.md`, `log_analysis.md`, `01_plan.md`, `02_review.md`, `03_plan_final.md`, `04_code_review_fix.md`, `05_deepcheck.md`, `06_audit.md`) |

`requirement`, `root_cause`, and `plan_review` are optional for staged runs that did not use the corresponding entry or step. `patches`, `delivery_report`, and `delivery_brief` are supplementary evidence. A missing metadata file, invalid mapping, or missing essential artifact is an evidence gap: report it precisely and use `SKIPPED` when the claim cannot be reconstructed. Do not repair the metadata or create placeholder files.

Also read the current `git diff` and any supplied test, build, or deployment evidence. Do not inspect legacy `.icode_output/` or Claude data as a substitute for an absent current artifact.

## Review workflow

1. Confirm read-only mode and list the evidence actually available.
2. Reconstruct the claimed symptom, root cause, change, verification, run layout, and workflow status. Separate facts from assumptions.
3. Review root cause and plan: verify the causal chain, rejected alternatives, and whether the selected change targets the cause.
4. Review implementation and contracts: inspect the diff for correctness, edge cases, state, concurrency, lifecycle, API/configuration/persistence compatibility, and ICode artifact/metadata consistency where relevant.
5. Review regression, security, and performance risk. Read [references/domain-checklists.md](references/domain-checklists.md) only for relevant risks.
6. Return the required report. If findings require a change, hand them back to `$icodex`; do not fix them here.

## Required output

Return exactly this structure:

```markdown
# External Review

## Reviewer

Claude CLI / Claude Code / Other, or SKIPPED with reason.

## Inputs

- Run directory: present / missing
- Metadata and layout: present / missing / invalid
- Artifacts read: logical keys and resolved paths, or missing
- git diff: present / missing
- Verification output: present / missing

## Root Cause Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

## Implementation Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

## Architecture and Contract Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

## Regression Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

## Security Review

PASS / FAIL / N/A / INSUFFICIENT_EVIDENCE

## Performance Review

PASS / FAIL / N/A / INSUFFICIENT_EVIDENCE

## Findings

Concrete findings only. Use `None` if there are no actionable findings.

## Final Decision

PASS / FIX_REQUIRED / SKIPPED
```

## Decision rules

- `PASS`: root cause, implementation, contracts, regression risk, and relevant verification evidence are acceptable.
- `FIX_REQUIRED`: one or more actionable correctness, compatibility, security, performance, or evidence-integrity findings remain.
- `SKIPPED`: the available run directory, metadata/artifact mapping, diff, or verification evidence cannot support a responsible review.

For `FIX_REQUIRED`, include file and line references where available, explain impact, and give the smallest actionable correction. For `SKIPPED`, name the missing evidence and the exact command or artifact needed to resume review.

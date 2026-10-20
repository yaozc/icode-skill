---
name: icodex-review
description: Use for read-only independent final review of an ICode run and an explicit dirty, commit, or base-head scope, including workflow contracts and current verification debt. Do not use for implementation.
---

# ICODEX Review

## Role and boundary

`$icodex-review` is an independent, read-only final reviewer. It reviews a supplied ICode run directory, an explicit dirty/commit/base-head scope, and available verification evidence after `$icodex` has completed local work.

It must not edit files, run formatters or generators, install MCPs, write metadata or artifacts, stage, commit, push, reset, clean, or implement fixes. Return the `EXTERNAL_REVIEW.md` content in the response; the caller decides whether to save it.

## Input discovery

First read the entire [references/workflow-contract.md](references/workflow-contract.md). Its READ_ONLY, SCOPE, ARTIFACTS, RISK, DECISIONS, REPLAN, ACCEPTANCE, EVIDENCE, RESULTS and LEGACY rules are mandatory. It is the single source for the workflow extensions, candidate binding and final-decision precedence; check them before ordinary engineering review. The local document checker is not a target-run validator or proof that an AI performed the review.

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

Only unused staged entry artifacts are optional. A staged run claiming completed step `2` must have a mapped `plan_review` artifact. Derive all required artifacts from the exact completed prefix and status. `patches`, `delivery_report`, and `delivery_brief` supplement that evidence. Missing essential evidence is a gap; contradictory state or a false completion claim is a violation. Do not repair metadata or create placeholder files.

Use the selected scope and safe Git reads specified by SCOPE. Dirty includes staged, unstaged and relevant untracked files; commit/base-head uses resolved SHAs and candidate file blobs. An empty working-tree diff does not establish an empty review scope. Read supplied test/build/deployment evidence and bind it to the selected candidate. Do not inspect legacy `.icode_output/` or Claude data as a substitute for an absent current artifact.

## Review workflow

1. Confirm read-only mode and list the evidence actually available.
2. Resolve the supplied scope, inventory changes, and bind evidence to the selected candidate. Reconstruct the claimed symptom, root cause, change, verification, run layout, and workflow status. Separate facts from assumptions.
3. Review root cause and plan: verify the causal chain, rejected alternatives, and whether the selected change targets the cause.
4. Review implementation and contracts: inspect the diff for correctness, edge cases, state, concurrency, lifecycle, API/configuration/persistence compatibility, and ICode artifact/metadata consistency where relevant.
5. Apply all workflow-contract rules: actual mode/prefix, decisions/replan, lifecycle expectations, latest matching evidence and debt. Review regression, security, and performance risk using relevant [references/domain-checklists.md](references/domain-checklists.md).
6. Return the required report. If findings require a change, hand them back to `$icodex`; do not fix them here.

## Required output

Return exactly this structure:

```markdown
# External Review

## Reviewer

Actual model and host, or SKIPPED with reason; never claim a different reviewer.

## Inputs

- Run directory: present / missing
- Metadata and layout: present / missing / invalid
- Artifacts read: logical keys and resolved paths, or missing
- Review scope: dirty / commit / base-head; requested refs and resolved SHA(s)
- Changes inspected: staged / unstaged / untracked / committed; exclusions and working-tree differences
- git diff: present / missing / empty, with the scope that produced it
- Verification output: present / missing
- Test evidence: observed cases, report identity, actual process result and missing proof; legacy/no-summary boundary

## Root Cause Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

## Implementation Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

## Architecture and Contract Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

For affected public interfaces, distinguish source compatibility, exports/layout/ownership, external compilation/linking, binary ABI compatibility and runtime behavior from supplied evidence.

## Workflow Contract Review

PASS / FAIL / INSUFFICIENT_EVIDENCE; actual mode, prefix, schema, decisions/replan, and current artifact generation.
Check frozen scope/attempt/phase and actual coverage evidence; a registered path or batch Read receipt alone never proves complete reading.

## Regression Review

PASS / FAIL / INSUFFICIENT_EVIDENCE

## Verification and Delivery Review

PASS / FAIL / INSUFFICIENT_EVIDENCE; required cells, matching baseline/evidence, latest outcomes, lifecycle coverage and remaining debt.
Report workflow status, implemented, delivery_verdict and direction verdict separately; none is Final Decision.
Inspect true case counts and process failures; zero/all-skipped is inconclusive. Apply optional test_summary history and candidate/cell selection rules from the shared contract; do not run target helpers to manufacture missing evidence.

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

- `PASS`: the explicit scope, root cause, implementation, contracts, regression risk and all applicable required verification have sufficient acceptable evidence. This is a scoped review conclusion, not automatic delivery verification.
- `FIX_REQUIRED`: confirmed correctness, compatibility, security, performance, contract or evidence-integrity violations remain. Confirmed violations take precedence: return FIX_REQUIRED even when evidence gaps also exist.
- `SKIPPED`: scope, artifacts or required verification cannot support a responsible conclusion and no confirmed violation takes precedence. Evidence gaps alone require SKIPPED, not an implementation failure.

For `FIX_REQUIRED`, include file and line references where available, explain impact, and give the smallest actionable correction. For `SKIPPED`, name the missing evidence and the exact command or artifact needed to resume review.

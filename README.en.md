# ICODEX Review

This is the read-only cross-model final review skill for ICODEX v2.17. Use it after another AI has completed `$icodex` implementation, self review, self audit, and verification. Review an explicit dirty/commit/base-head change scope.

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
$icodex-review Review .ai/icode/{run_dir}, scope dirty. Only output EXTERNAL_REVIEW.md. Do not modify code.
```

## Inputs and Review Scope

Read the [shared review contract](references/workflow-contract.md), then resolve current artifacts through `artifact_layout` and `artifact_map`. Mapped `full/` and `replan/` revisions are valid; never guess numbered filenames.

For committed code, supply commit or base/head; an empty working-tree diff never authorizes a pass.

```text
$icodex-review Review .ai/icode/{run_dir}, scope commit <commit>. Only output EXTERNAL_REVIEW.md.
$icodex-review Review .ai/icode/{run_dir}, scope base <base> head <head>. Only output EXTERNAL_REVIEW.md.
```

Dirty review inventories staged, unstaged and untracked files separately and reports exclusions. Commit/base-head records resolved SHAs and matches `source_hashes` against candidate file blobs; current working-tree evidence cannot automatically validate a historical candidate. Disable external diff, textconv, fsmonitor and optional index writes during Git reads.

Compare working-tree content with raw commit/index blobs using trusted built-in tools; never use working-tree git diff/status because clean/process filters can execute.

Set GIT_NO_LAZY_FETCH=1 and --no-pager for every Git read; missing objects are evidence gaps and never authorize automatic fetch or remote helpers/pagers.

Never execute code or helpers from the reviewed repository.

## Workflow Extensions

| Check | Review obligation |
|---|---|
| Mode and artifacts | Derive required mappings from the completed prefix; completed step 2 requires `plan_review`. Use `risk_profile.effective_mode` for full/fast, review budget and deepcheck evidence, not the original request |
| Decisions and replan | Inspect `semantic_decisions`, `requirement_deltas`, `replan_state`; old mappings cannot complete a new generation, and diagnosis cannot claim implemented delivery |
| Lifecycle | When `acceptance_contract.required`, inspect four phases × four consumers (16 expectations), then separately inspect runtime proof |
| Layered evidence | Inspect sparse `verification_contract.required_cells`, latest matching `verification_runs`, execution-time `baseline` and current evidence hashes; host/simulated cannot substitute for physical |
| Legacy | Missing `workflow_contract_version` permits scoped legacy review; unsupported explicit versions cannot be treated as legacy, and new fields must not be filled in during review |

Workflow completion does not establish delivery verification.

Report workflow status, implemented, `delivery_verdict`, direction verdict and external review conclusion separately. Missing modern fields never makes legacy delivery verified; undefined scope or insufficient relevant proof remains an evidence gap.

Evidence gaps alone require SKIPPED; confirmed violations take precedence with FIX_REQUIRED.

Exit code 0 alone does not prove test success; zero/all-skipped cases are inconclusive and known failures cannot be downgraded.

Check optional test_report/test_summary/test_exit_code against real report counts, original identity, the current candidate/cell and exact history replay. Do not fabricate summaries for old runs or execute reviewed tests/helpers to obtain missing evidence.

Review source compatibility, binary ABI compatibility and runtime behavior separately; Read registration does not prove actual reading or complete coverage.

## Output

Preserve Root Cause Review, Implementation Review, Architecture and Contract Review, Regression Review, Security Review, Performance Review, Findings and Final Decision. Add Workflow Contract Review, Verification and Delivery Review, scope/SHA/candidate matching and debt details. Final Decision remains `PASS`, `FIX_REQUIRED` or `SKIPPED`; PASS applies only to an explicit scope with sufficient evidence.

## Maintenance and Contract Regression

```bash
python3 -B tools/lint_review_contract.py .
python3 -B -m unittest discover -s tests -v
```

The contract checker validates document rules and Git examples, not whether an AI correctly performed a review.

Regressions delete or reverse critical normative sentences, report interfaces and bilingual explanations; check broken links and malformed files; and exercise staged/unstaged/untracked changes, commit/root commit/historical scopes, candidate hash mismatch, dangerous refs and disabled configuration-driven programs in isolated Git repositories. The checker reads skill documents only; it neither validates nor modifies target runs. Fixture writes occur only in temporary directories when a maintainer explicitly runs the tests.

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

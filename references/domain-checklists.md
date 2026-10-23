# Engineering Risk Checklists

Load only the sections relevant to the current task.

## Root Cause

- Symptom, trigger, and root cause are clearly separated.
- The causal chain is supported by observations, logs, tests, or code paths.
- Rejected hypotheses have counter-evidence, not just intuition.
- The fix targets the cause, not only the visible failure.

## State and Workflow

- State transitions are explicit and valid for success, failure, timeout, and cancellation.
- Partial progress, retry, rollback, and recovery paths are intentional.
- Invalid or duplicate events cannot corrupt state.
- User-visible or caller-visible outcomes are deterministic.

## Async and Concurrency

- Async gaps, late callbacks, cancellation, and timeout paths are handled.
- Shared mutable state has clear synchronization or sequencing.
- Work cannot complete twice, hang forever, or silently disappear.
- Cleanup runs exactly once for subscriptions, timers, handles, jobs, and background work.

## Resource Ownership

- Ownership boundaries are explicit for memory, handles, connections, files, tasks, and cached data.
- Create/open/start paths have matching close/dispose/stop paths.
- Errors do not leak resources or leave partially initialized state.
- Shutdown and retry paths preserve invariants.

## Resource Budgets and Performance Evidence

Review raw input limits, parser expansion and elapsed-time guarantees separately.

- Check per-file and cumulative bytes, entry/event counts, actual allowed paths, parse expansion and peak live memory. A higher single-file budget does not raise every limit; a soft deadline around I/O does not prove interruptible I/O or a hard elapsed-time bound.
- `del`, weak-reference expiry and reduced history lifetime only show those objects can be released. Require supplied candidate/workload/environment measurements before claiming a peak-memory or throughput improvement.
- Pure-data reuse must not cache authorization, freshness or evidence eligibility. Releasing old history must not omit fresh validation; incomplete coverage, timeouts, links and read races remain visible. Do not run target pressure tests or helpers to fill gaps.

## Architecture and Contracts

- Dependency direction remains consistent with the project.
- Ownership boundaries are explicit and unchanged unless the plan says otherwise.
- Side effects are localized and testable.
- Public contracts and serialized formats remain compatible.
- Error handling is intentional rather than swallowed or converted into silent success.

## Collection and History Semantics

Distinguish declared unordered membership from ordered observations and decisions.

- Identify the producer version and field contract first. For an explicitly unordered collection, compare exact complete members, required types and duplicate prohibition; only member permutations are equivalent. JSON object-key order alone carries no array-order claim.
- Preserve `verification_runs`, `patch_history`, event history, accepted prefixes and any contract-defined review/decision order. Sorting or deduplicating those histories cannot hide a later negative result, repair lineage or change which record is latest.
- Do not require stage/provider fields from a producer that lacks that feature. A feature being disabled does not validate ordinary ticket/evidence claims. For an actually enabled feature, missing locator/binding/history or exhausted discovery is not proof that it was never enabled.

## Authorization and Sensitive Evidence

Inspect authorization provenance independently of scanner output and permission prose.

- Bind the actual user/trusted authorization source to the action, target and limits. Scanner success, zero violations, exit 0 or a note cannot grant permission or expand an existing grant. Finite lexical matching does not resolve natural-language intent.
- A disclaimer containing "authorization" is not automatically a secret. Inspect actual credential values, assignments or authentication headers without reproducing them; a scanner exception proves neither secret absence nor authorization.
- Missing authorization proof is a gap; an independently established unauthorized action is a violation. Keep the review read-only rather than rerunning a target scanner or operation.
- Host simulation is not a native runtime observation. MCP installation/configuration does not prove process reload; access policy refusal is not file absence. Keep explicit PATH/access roots and supplied host/execution/artifact identities visible.

## Public Library API/ABI

Inspect supplied public headers, exported symbols and old consumer binary evidence separately.

- Apply only to an affected exposed library/package/binding boundary and its compatibility promise; ordinary application or document edits do not require arbitrary ABI tools or consumer languages.
- Bind baseline/candidate, installed header/package and artifact hashes, compiler/runtime and architecture. Inspect public/deprecated wrappers, calling convention, visibility, layout/alignment, ownership, callback lifetime and error/exception translation where exposed.
- Report source compatibility, external compilation/linking, binary ABI compatibility and runtime behavior separately. Same declarations, in-tree tests or a rebuilt consumer cannot replace a promised old-binary run. Missing evidence stays unresolved; consume supplied tool output without executing target code or tools.

## Inspection Scope and Coverage

A registered path or Read receipt is not evidence of actual review coverage.

- Compare frozen scope/related consumers, source hash, baseline and attempt/phase. A larger max_files or batch admission does not reduce reading obligations; a new round starts fresh reads/assessments/findings.
- For producers supporting --max-files/--paths-json, compare the frozen positive budget, exact batch and current round; successful registration does not establish enumeration or actual reading. Older producers need no new option/metadata fields.
- Equivalent declaration reuse must preserve the complete required set and checks; new consumers, truncation and unknown coverage remain visible. Known unread scope contradicting claimed completeness is a violation; missing support alone is a gap.

## ICode Artifact and Metadata Contract

- Read all rules in [workflow-contract.md](workflow-contract.md) before applying this engineering checklist.
- The review identifies `artifact_layout` and resolves evidence through `artifact_map` before reading workflow artifacts.
- Concise and staged layouts are not mixed: absent optional entry artifacts are reported as absent, not invented.
- Metadata, mapped artifacts, patches, and verification evidence agree on the claimed workflow state.
- Missing essential evidence is a gap; invalid mappings or evidence contradicting claimed completion/verification are confirmed violations. The reviewer does not repair metadata, rename artifacts, or create placeholders.
- Check exact completed prefixes and state consistency; a staged run claiming completed step `2` requires `plan_review`.
- Assess actual `effective_mode`, risk evidence and current upgrade/replan mappings; old fast artifacts cannot satisfy full work.
- Check `semantic_decisions`, `requirement_deltas` and `replan_state`, including diagnostic intent and preserved review hypotheses.

## Lifecycle and Delivery Evidence

- Check required `acceptance_contract` expectations for all 16 phase/consumer cells, then separately check lifecycle proof.
- Use sparse `verification_contract.required_cells` and the latest matching `verification_runs` record, including environment and phase.
- Bind execution-time baseline to the selected dirty/commit/base-head candidate and verify source, contract, revision, patch count and evidence hashes.
- Host or simulated evidence cannot satisfy a physical requirement; required missing or stale evidence remains debt.
- Keep workflow status, `delivery_verdict`, direction `verdict` and external review PASS separate. Confirmed violations take precedence over gaps; gaps alone require SKIPPED.
- No-version legacy and explicit unsupported versions have different handling. Never repair or migrate either during review.

## Test Execution and Report Evidence

Compare test_summary with supplied runner output and the true process result.

- Exit 0 is insufficient: zero-case/all-skipped is inconclusive; failed/errors, nonzero exit, timeout or a failed assertion cannot be promoted to pass or hidden as uncertain. Report pass is limited to actual cases.
- Optional test_report is read by the producer; test_summary is machine-derived, not caller-supplied. Check actual testcase totals, sum/outcome, original path/hash/bytes and applicable run/cell/baseline. A summary authenticates observed bytes, not live execution or complete coverage.
- When the report is explicit evidence too, compare its saved summary hash with evidence_hashes, including equivalent relative paths. Contradictions are violations; do not execute helpers or repair evidence to reconcile them.
- Within a current candidate/cell, an uncounted pass cannot mask existing report evidence; later negative results still win. Exact retries return historical observations, new runs reread reports. Absent historical report files alone do not erase summaries; explicitly required evidence files retain their hash checks.
- Old no-summary runs are not automatically invalid or verified. Use available original output, mark missing proof and keep read-only boundaries; do not run target tests, fetch dependencies or fabricate counts.

## Regression and Compatibility

- Retry loops are bounded and observable.
- Existing callers and workflows keep their expected behavior.
- Persisted data, serialized formats, APIs, and configuration remain compatible or have a migration path.
- Logs and errors identify state, event, and reason without leaking sensitive data.
- Tests or manual checks cover the original failure and likely neighboring regressions.

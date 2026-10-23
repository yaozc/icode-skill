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

## Architecture and Contracts

- Dependency direction remains consistent with the project.
- Ownership boundaries are explicit and unchanged unless the plan says otherwise.
- Side effects are localized and testable.
- Public contracts and serialized formats remain compatible.
- Error handling is intentional rather than swallowed or converted into silent success.

## Public Library API/ABI

Apply this profile only to an affected public library, package, or binding boundary and its compatibility promise.

Ordinary application or document changes do not require ABI tools or an arbitrary matrix of consumer languages, compilers, and architectures. For non-native packages, use the language's published API and dependency-resolution evidence; mark native symbol/layout checks not applicable when the boundary does not expose them.

- Bind the comparison to baseline and candidate revisions, the public installed header/package, the actual library artifact hash, compiler/runtime ABI, target architecture and relevant build options. Confirm what the external consumer actually resolves; a matching repository header alone is insufficient.
- Trace the exact customer-visible declaration, language linkage, overload, export macro, calling convention, qualifiers, defaults and exception contract through public/deprecated wrappers to the implementation and exported symbol. An internal replacement is not automatically public, and deprecated wrappers retain their promised behavior.
- Inspect the selected artifact's actual exports, symbol names/mangling, visibility and version. Check exposed layout, size/alignment/offsets, packing and enum representation where relevant, plus allocation/deallocation pairing, buffer/callback lifetime and thread constraints. Check units, sentinels, null/default handling, error translation and failure cleanup; prohibited exceptions must not cross a C boundary.
- Build the smallest external consumer against the selected installed/package interface and artifact when validation is authorized. Record compilation, linking, dependency resolution and execution separately; in-tree tests and declarations alone do not prove external availability.

When backward binary compatibility is promised, exercise a preserved old consumer binary against the candidate without recompiling it.

Exercise the affected entry and its lifetime/cleanup path in the promised target environment. A freshly rebuilt consumer can support source/link claims, but cannot replace the old-binary observation. Host or simulated execution cannot establish an unobserved target runtime result.

Source compatibility, binary ABI compatibility, and runtime behavior are separate claims.

Record declaration comparison, exports/layout, external compilation/linking and old-binary execution as distinct evidence layers in the existing review/verification artifacts, with commands, actual outputs, selected identities and observed scope. New metadata fields are not required. Tool exit 0 is limited to its actual check, and a pass in one layer cannot promote another.

Missing baseline, artifact, compiler, or target environment leaves the corresponding layer unresolved.

Keep the checks completed and name the smallest missing observation. Do not install tools, run unavailable binaries or access a target merely to eliminate a gap without authorization; continue using the existing verification debt rather than claiming full compatibility from static inspection. This checklist and its document linter do not establish that an AI performed the review or that a library is compatible.

## Regression and Compatibility

- Retry loops are bounded and observable.
- Existing callers and workflows keep their expected behavior.
- Persisted data, serialized formats, APIs, and configuration remain compatible or have a migration path.
- Logs and errors identify state, event, and reason without leaking sensitive data.
- Tests or manual checks cover the original failure and likely neighboring regressions.

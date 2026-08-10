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

## Regression and Compatibility

- Retry loops are bounded and observable.
- Existing callers and workflows keep their expected behavior.
- Persisted data, serialized formats, APIs, and configuration remain compatible or have a migration path.
- Logs and errors identify state, event, and reason without leaking sensitive data.
- Tests or manual checks cover the original failure and likely neighboring regressions.

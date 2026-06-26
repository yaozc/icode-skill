# Domain Checklists

Load only the sections relevant to the current task.

## Flutter

- Widget lifecycle: `mounted`, `dispose`, async gaps, context validity.
- Navigation: route lifetime, duplicate pops, stale context, dialog ownership.
- State management: Riverpod/provider listener lifetime, notifier disposal, stale state.
- Streams and timers: cancellation, double subscription, late events after disposal.
- UI regression: loading, error, empty, retry, background/foreground transitions.

## BLE

- Connection state machine: scanning, connecting, connected, disconnecting, disconnected.
- Timeout and retry: no infinite waits, bounded retry policy, user-visible failure path.
- Callback ownership: late callbacks, duplicate callbacks, missing completion/error.
- MTU and characteristic handling: negotiation, partial writes, notification subscription.
- Recovery: disconnect, reconnect, device power loss, permission changes, Bluetooth off/on.

## Linux

- Threads: join/detach ownership, cancellation path, shared data lifetime.
- Synchronization: mutex ordering, condition-variable predicates, deadlocks, races.
- File descriptors: close-on-error, duplicate ownership, epoll/select cleanup.
- Signals: async-signal safety, interrupted syscalls, shutdown ordering.
- Memory: allocation ownership, double free, leaks, use-after-free.

## Architecture

- Dependency direction remains consistent with the project.
- Ownership boundaries are explicit and unchanged unless the plan says otherwise.
- Side effects are localized and testable.
- Public contracts and serialized formats remain compatible.
- Error handling is intentional rather than swallowed or converted into silent success.

## Embedded and Recovery

- State machines have explicit transitions for success, failure, timeout, and cancellation.
- Power/network/device-loss scenarios have deterministic recovery paths.
- Retry loops are bounded and observable.
- Logs identify state, event, and reason without leaking sensitive data.
- Backward compatibility is considered for old firmware, old app versions, or stale persisted state.

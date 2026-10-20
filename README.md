# ICode v2.17 for Codex

ICode is a Codex skill for root-cause-first software delivery. It combines a continuous Codex workflow with the upstream v2.17 staged workflow, while keeping Codex storage, same-model review, resumable state, and safe MCP registration.

This port is based on [`ayukyo/icode-skill`](https://github.com/ayukyo/icode-skill) v2.17.

Compatible fixes through upstream `main@5be9dee` are selectively ported for large-repository crosschecks, Windows I/O and locks, and safe synchronization. The [port record](docs/superpowers/specs/2026-10-14-main-codex-selective-port-design.md) documents the selection and Codex adaptations; the v2.17 workflow and Codex storage contracts remain in place.

## Install

Clone or synchronize the repository to:

```bash
git clone <your-fork-url> ~/.codex/skills/icodex
```

The skill is invoked as `$icodex`. To preview or install its optional MCP servers:

```bash
bash ~/.codex/skills/icodex/mcp/install-codex.sh --dry-run
bash ~/.codex/skills/icodex/mcp/install-codex.sh
```

The adapter uses only `codex mcp list|get|add|remove`. Identical configurations are skipped; different same-name configurations are refused with exit code 2 and are never removed or overwritten.

## Two execution modes

Use `$icodex <task>` for Codex full mode:

```text
Diagnose → Plan → Implement → Senior Reviewer self-review
         → Principal Engineer audit → Verify
```

It writes concise artifacts such as `RCA.md`, `PLAN.md`, `IMPLEMENT.md`, `SELF_REVIEW.md`, and `AUDIT.md`.

Use explicit commands for staged mode:

```text
01 Plan → 02 Review → 03 Finalize → 04 Code → 05 Deep Check → 06 Audit
```

`$icodex start` is the standard automatic staged 1→6 chain. `$icodex plan` executes only step 1 and then pauses. `$icodex fast` is the reduced staged chain.

`$icodex fast` assesses the [nine business risk flags](references/fast_risk.md). Any trigger upgrades the same ticket to the complete staged workflow, with multiple review rounds, adversarial review, and Reverse/Fixed/Free deep checks. Low-risk work stays fast. Resume interrupted tickets with `$icodex start` without arguments; late risk discovery repeats full review while preserving existing source and historical artifacts.

## Commands

| Command | Purpose |
|---|---|
| `$icodex help` | Read-only command help |
| `$icodex init [requirement]` | Step 0 requirement draft and discussion |
| `$icodex log [logs/symptoms]` | Root-cause analysis entry |
| `$icodex plan [requirement]` | Staged step 1, then pause |
| `$icodex start [requirement]` | Standard automatic staged steps 1→6 |
| `$icodex review [N]` | Staged step 2 |
| `$icodex merge` | Staged step 3 |
| `$icodex code` | Staged step 4 |
| `$icodex deepcheck` | Staged step 5 |
| `$icodex audit` | Staged step 6 |
| `$icodex crosscheck [target]` | Persistent multi-round review of a completed run; target remains read-only |
| `$icodex verify [options]` | Read verification debt/context or explicitly record actual evidence; completion and verification are separate |
| `$icodex fast [requirement]` | Reduced for low risk; risk triggers upgrade the same ticket to the complete staged workflow |
| `$icodex patch [change]` | Append a verified patch to an existing run |
| `$icodex doc [request]` | Project/module knowledge base |
| `$icodex limit [request]` | Project constraints and red lines |
| `$icodex readme` | Delivery report and cross-domain brief |
| `$icodex status [options]` | State, verdict, and artifact validation |
| `$icodex list [query]` | Read-only cross-project ticket search |
| `$icodex install [name]` | Safe Codex MCP registration |

`$icodex crosscheck` persists isolated review records under `.ai/icode/.crosscheck/` without changing the target run or source. Independent cross-model `$icodex-review` remains zero-write and returns its report only in the response.

## Storage and recovery

New project runs are written only under `.ai/icode/<run-name>/`. New global data is written only under `~/.codex/icode_data/`.

Every persisted run contains `.ico_metadata.json` and a stable `artifact_map`. State transitions, artifact publication, patch numbering, index updates, and legacy migrations use [`tools/icode_state.py`](tools/icode_state.py), which provides atomic replacement and bounded file locks.

Legacy `.icode_output/` runs and `~/.claude/icode_data/` are read-only compatibility sources. Read views merge Codex and legacy data per key with Codex precedence. Continuing a legacy run first performs a deterministic, manifest-verified, resumable `prepared → completed` migration; the legacy source is never modified.

## Safety guarantees

- Active Codex paths never write `~/.claude.json` or run legacy Claude installers.
- MCP conflicts are detected before dependency installation or registration.
- Artifact paths cannot escape the run directory.
- Full and staged state arrays must be exact ordered prefixes.
- Index, run metadata, patch reservations, and migrations are lock-protected.
- A failed index publication resumes from the already prepared migration directory.

See [SKILL.md](SKILL.md) for routing and [the Codex runtime contract](references/codex_runtime.md) for persistence rules.

## Verification

Verification records optionally accept a project-relative `test_report` (real JUnit XML) and an integer `test_exit_code` through the existing `record-verification --input-json` interface. The writer derives `test_summary`; caller-supplied counts are rejected. Zero/all-skipped cases are inconclusive, known failures stay fail, and an uncounted pass cannot mask report-backed evidence for the same current baseline/cell. Saved summaries describe observed report bytes; actual execution still needs runner output and provenance. See the [test evidence contract](references/workflow_contract.md#测试报告证据).

Install `pytest` in your test environment before running the suite.

```bash
python3 -m pytest -q tests
bash tests/test_mcp_codex_install.sh
python3 tools/lint_codex_contract.py .
```

License: [MIT](LICENSE).

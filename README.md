# ICode v2.17 for Codex

ICode is a Codex skill for root-cause-first software delivery. It combines a continuous Codex workflow with the upstream v2.17 staged workflow, while keeping Codex storage, same-model review, resumable state, and safe MCP registration.

This port is based on [`ayukyo/icode-skill`](https://github.com/ayukyo/icode-skill) v2.17.

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

`$icodex plan` and `$icodex start` execute only step 1 and then pause. `start` is a compatibility alias for `plan`. `$icodex run` is the automatic staged 1→6 chain. `$icodex fast` is the reduced staged chain.

## Commands

| Command | Purpose |
|---|---|
| `$icodex help` | Read-only command help |
| `$icodex init [requirement]` | Step 0 requirement draft and discussion |
| `$icodex log [logs/symptoms]` | Root-cause analysis entry |
| `$icodex plan [requirement]` | Staged step 1, then pause |
| `$icodex start [requirement]` | Alias for `plan`, then pause |
| `$icodex review [N]` | Staged step 2 |
| `$icodex merge` | Staged step 3 |
| `$icodex code` | Staged step 4 |
| `$icodex deepcheck` | Staged step 5 |
| `$icodex audit` | Staged step 6 |
| `$icodex run [requirement]` | Automatic staged steps 1→6 |
| `$icodex fast [requirement]` | Reduced staged workflow |
| `$icodex patch [change]` | Append a verified patch to an existing run |
| `$icodex doc [request]` | Project/module knowledge base |
| `$icodex limit [request]` | Project constraints and red lines |
| `$icodex readme` | Delivery report and cross-domain brief |
| `$icodex status [options]` | State, verdict, and artifact validation |
| `$icodex list [query]` | Read-only cross-project ticket search |
| `$icodex install [name]` | Safe Codex MCP registration |

Independent cross-model review remains outside this skill. After local verification, hand the artifact directory, diff, and test evidence to `$icodex-review`.

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

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash tests/test_mcp_codex_install.sh
python3 tools/lint_codex_contract.py .
```

License: [MIT](LICENSE).

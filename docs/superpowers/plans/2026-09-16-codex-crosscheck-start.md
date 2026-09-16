# Codex Crosscheck 与 Start 串联 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `codex` 分支提供可持久化、可多轮、零回写目标工单的 `$icodex crosscheck`，并让 `$icodex start` 与 `$icodex run` 等价地自动串联步骤 1→6。

**Architecture:** 以现有 `tools/icode_state.py` 作为 Codex 工单身份与 metadata 校验真源，新增只读 ticket resolver；从上游移植 crosscheck、inspection worklist 与 schema，但将全部控制路径改成 `.ai/icode`，并排除这些控制文件对 Git/源码快照的影响。命令路由仍由 Markdown skill 合同驱动，`start` 和 `run` 共用 `steps/run.md`，`plan` 独立停在步骤 1。

**Tech Stack:** Python 3 标准库、JSON Schema draft-07、pytest/unittest、POSIX shell、Markdown contract lint。

## Global Constraints

- 新工单与 crosscheck 只写 `.ai/icode/`；新全局数据只读写 `~/.codex/icode_data/`。
- `.icode_output/` 与 `~/.claude/icode_data/` 仅作明确的 legacy 只读兼容源，不得成为新 crosscheck 的读写目标。
- `$icodex-review` 保持一次性、完全无写入；本计划不修改 `external-review` 分支。
- Crosscheck 只能写 `.ai/icode/.crosscheck/icode_N/`，不得写目标工单、源码、索引、anchors、patch history 或 verification records。
- `$icodex start` 与 `$icodex run` 行为完全一致并自动串联 1→6；`$icodex plan` 只执行步骤 1。
- 所有持久化工单都必须通过 `tools/icode_state.py` 校验；身份歧义、路径逃逸、输入漂移和 schema 不一致均 fail-closed。
- 不引入 `icode_control.py`、Agent Runtime、UI 或新第三方依赖。

---

### Task 1: Codex ticket resolver 与完成态目标校验

**Files:**
- Modify: `tools/icode_state.py`
- Modify: `tests/test_icode_state.py`

**Interfaces:**
- Produces: `resolve_ticket(project_root: Path, codex_root: Path, ticket_id: str) -> Path`
- Produces: `validate_completed_run(run_dir: Path, project_root: Path) -> dict[str, Any]`
- Produces: CLI `icode_state.py resolve-ticket --ticket ID --project-root ROOT --codex-root ROOT`
- Consumed by: `tools/icode_crosscheck.py` in Task 3.

- [ ] **Step 1: Write resolver and validation failure tests**

Add tests that create `.ai/icode/icode_1/.ico_metadata.json`, mapped artifact files, `src/example.py`, and a Codex index. Assert the local/index identity resolves once, legacy overlays are ignored, and disagreement fails:

```python
def test_resolve_ticket_requires_one_consistent_codex_identity(self) -> None:
    run_dir = self.project / ".ai/icode/icode_1"
    metadata = completed_metadata(ticket_id="demo-1", code_files=["src/example.py"])
    materialize_run(run_dir, metadata)
    self.write_index([{
        "ticket_id": "demo-1",
        "project_path": str(self.project),
        "out_dir": ".ai/icode/icode_1",
        "status": "completed",
    }])
    self.assertEqual(resolve_ticket(self.project, self.codex_root, "demo-1"), run_dir.resolve())

    self.write_index([{
        "ticket_id": "demo-1",
        "project_path": str(self.project),
        "out_dir": ".ai/icode/icode_2",
        "status": "completed",
    }])
    with self.assertRaisesRegex(ValueError, "index.*metadata|identity"):
        resolve_ticket(self.project, self.codex_root, "demo-1")
```

Also add cases for zero matches, duplicate local metadata, `legacy_overlay=true`, non-completed status, missing stable artifact key, `../` artifact escape, missing mapped file, absolute `code_files`, `..` code escape, symlink code escape, and directory-valued code file.

- [ ] **Step 2: Run the focused tests to prove RED**

Run: `python3 -m pytest tests/test_icode_state.py -q`

Expected: new tests fail because `resolve_ticket` and `validate_completed_run` do not exist.

- [ ] **Step 3: Implement native-only candidate resolution**

Add pure helpers that scan only numbered local runs and native Codex index entries:

```python
CODEX_RUN_RE = re.compile(r"^icode_([1-9][0-9]*)$")

def resolve_ticket(project_root: Path, codex_root: Path, ticket_id: str) -> Path:
    project_root = Path(project_root).resolve()
    local = set(_local_ticket_candidates(project_root, ticket_id))
    indexed = set(_indexed_ticket_candidates(project_root, Path(codex_root), ticket_id))
    if local and indexed and local != indexed:
        raise ValueError("ticket index and metadata identities disagree")
    candidates = local | indexed
    if len(candidates) != 1:
        raise ValueError(f"ticket resolution requires exactly one candidate; found {len(candidates)}")
    return next(iter(candidates))
```

`out_dir` is interpreted relative to the matching canonical `project_path`; absolute/out-of-project index paths are rejected. Never call `load_merged_index`, never mutate index fields, and never fall back to latest.

- [ ] **Step 4: Implement completed-run validation and CLI JSON output**

Reuse `validate_metadata`, then enforce exact completed state and safe `code_files`:

```python
def validate_completed_run(run_dir: Path, project_root: Path) -> Dict[str, Any]:
    metadata = _read_json(Path(run_dir) / ".ico_metadata.json")
    errors = validate_metadata(metadata, Path(run_dir))
    if metadata.get("status") != "completed":
        errors.append("status must be completed for crosscheck")
    errors.extend(_validate_code_files(metadata.get("code_files"), Path(project_root)))
    if errors:
        raise ValueError("completed run validation failed: " + "; ".join(errors))
    return metadata
```

For a `demo-1` fixture, the CLI prints `{"resolved": true, "ticket_id": "demo-1", "run_dir": "/tmp/project/.ai/icode/icode_1", "project_root": "/tmp/project"}` only for one valid target and returns nonzero JSON for all rejected cases.

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m pytest tests/test_icode_state.py -q`

Expected: PASS.

```bash
git add tools/icode_state.py tests/test_icode_state.py
git commit -m "feat: add read-only Codex ticket resolution"
```

### Task 2: Port inspection worklist with Codex control-path exclusion

**Files:**
- Create: `tools/inspection_worklist.py`
- Create: `tests/test_inspection_worklist.py`
- Create: `tools/selfcheck_inspection_worklist.sh`
- Create: `tests/test_inspection_worklist_contract.sh`

**Interfaces:**
- Produces: `build_worklist(workspace, code_files, *, step, ticket_id, attempt, mode="full", related=None, scopes=None, baselines=None, max_files=200, max_bytes=1048576) -> dict`
- Produces: `validate_worklist(report, workspace, code_files=None, step=None, ticket_id=None, attempt=None, allow_incomplete=False) -> list[str]`
- Consumed by: crosscheck start/freeze/finish in Task 3.

- [ ] **Step 1: Port upstream tests and add `.ai/icode` regressions**

Start from `upstream/main:tests/test_inspection_worklist.py` and adapt the unsafe path parameterization:

```python
@pytest.mark.parametrize("path", [
    ".ai/icode/icode_1/03_plan_final.md",
    ".ai/icode/.crosscheck/icode_1/crosscheck_manifest.json",
    ".icode_output/.icode_output_1/03_plan_final.md",
])
def test_control_sidecars_are_never_source_units(api, repo, path):
    put(repo, path, "sidecar\n")
    with pytest.raises(ValueError):
        api.build_worklist(repo, [path], step="crosscheck", ticket_id="t", attempt=1)

def test_untracked_codex_sidecars_do_not_enter_candidates(api, repo):
    put(repo, ".ai/icode/.crosscheck/icode_1/fresh.json", "{}\n")
    report = build(api, repo)
    assert all(not item["path"].startswith(".ai/icode/") for item in files(report).values())
```

- [ ] **Step 2: Run the focused tests to prove RED**

Run: `python3 -m pytest tests/test_inspection_worklist.py -q`

Expected: FAIL because the tool is absent.

- [ ] **Step 3: Port the upstream stdlib implementation and adapt exclusions**

Copy the upstream behavior, retaining bounded Git calls, symlink checks, source hashes, read declarations, and finding location validation. Replace the control-path predicate with one shared helper:

```python
def _is_control_path(path: str) -> bool:
    parts = tuple(part.lower() for part in Path(path).parts)
    return ".icode_output" in parts or any(
        parts[index:index + 2] == (".ai", "icode")
        for index in range(max(0, len(parts) - 1))
    )

CONTROL_EXCLUDES = [
    ":(glob,exclude)**/.icode_output/**",
    ":(glob,exclude)**/.ai/icode/**",
]
```

Use `CONTROL_EXCLUDES` for diff, tracked, untracked, association, and outside-scope enumeration; call `_is_control_path` again before adding a candidate.

- [ ] **Step 4: Add and run shell selfchecks**

Port the upstream selfcheck and contract shell scripts, replacing expected `.icode_output` active paths with `.ai/icode` while retaining `.icode_output` as a blocked legacy path.

Run:

```bash
python3 -m pytest tests/test_inspection_worklist.py -q
bash tests/test_inspection_worklist_contract.sh
bash tools/selfcheck_inspection_worklist.sh
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/inspection_worklist.py tools/selfcheck_inspection_worklist.sh tests/test_inspection_worklist.py tests/test_inspection_worklist_contract.sh
git commit -m "feat: add Codex inspection worklists"
```

### Task 3: Port persistent crosscheck controller, schemas, and lifecycle tests

**Files:**
- Create: `tools/icode_crosscheck.py`
- Create: `schemas/crosscheck-manifest.schema.json`
- Create: `schemas/crosscheck-round.schema.json`
- Create: `tests/test_crosscheck.py`
- Create: `tests/test_crosscheck_contract.sh`
- Create: `tests/test_crosscheck_demo_sim.sh`
- Create: `tools/selfcheck_crosscheck.sh`

**Interfaces:**
- Consumes: `resolve_ticket` and `validate_completed_run` from Task 1.
- Consumes: worklist API from Task 2.
- Produces: CLI subcommands `start`, `inspection`, `freeze`, `finish`, `validate`.
- Produces: isolated containers `<project>/.ai/icode/.crosscheck/icode_N/`.

- [ ] **Step 1: Port upstream lifecycle tests to Codex fixtures**

Start from `upstream/main:tests/test_crosscheck.py`. Build valid Codex metadata using all stable artifact keys and real mapped files, then change fixture paths and tree exclusions:

```python
ticket = root / ".ai" / "icode" / "icode_1"

def tree_digest(root: Path, *, exclude_crosscheck: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if exclude_crosscheck and rel.parts[:3] == (".ai", "icode", ".crosscheck"):
            continue
        if path.is_symlink():
            digest.update(f"L:{rel}:{os.readlink(path)}\n".encode())
        elif path.is_file():
            digest.update(f"F:{rel}:".encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()

def test_crosscheck_outputs_do_not_make_finish_stale(workspace):
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    complete_round(started, env)
    result = run_tool(env, "finish", "--dir", started["crosscheck_dir"], "--round", "1")
    assert result["state"] == "completed"
```

Add tests for invalid artifact maps, unsafe code files, target/output symlinks, duplicate containers, fresh immutability, second-round finding coverage, input drift, zero target writes, and no `.ico_metadata.json` inside crosscheck containers.

- [ ] **Step 2: Run crosscheck tests to prove RED**

Run: `python3 -m pytest tests/test_crosscheck.py -q`

Expected: FAIL because the controller and schemas are absent.

- [ ] **Step 3: Port controller constants and target resolution**

Port `upstream/main:tools/icode_crosscheck.py`, then make these contract changes:

```python
CONTAINER_RE = re.compile(r"^icode_([1-9][0-9]*)$")
TRANSIENT_TARGET_FILES = {".ico.lock", ".index.lock", ".migration.lock"}

def safe_crosscheck_root(project_root: Path, override=None) -> Path:
    expected = project_root.resolve() / ".ai" / "icode" / ".crosscheck"
    if override is not None and Path(override).expanduser().absolute() != expected.absolute():
        raise CrosscheckError("crosscheck root is fixed to .ai/icode/.crosscheck")
    if any(path.is_symlink() for path in (expected.parent.parent, expected.parent, expected)):
        raise CrosscheckError("crosscheck path must not contain symlinks")
    expected.mkdir(parents=True, exist_ok=True)
    if expected.resolve().parent != (project_root.resolve() / ".ai" / "icode"):
        raise CrosscheckError("crosscheck root escaped the project control directory")
    return expected

def resolve_with_state(ticket_id: str, workspace: Path) -> Path:
    return state.resolve_ticket(workspace, Path.home() / ".codex" / "icode_data", ticket_id)
```

Path input walks upward only until it finds a metadata file below `<project>/.ai/icode/icode_N`; `--ticket` uses the resolver; no-argument mode requires the step layer to pass its already-bound run directory and never guesses latest.

- [ ] **Step 4: Enforce target validation and self-output filtering**

At `start`, `finish`, and target re-resolution inside `validate`, call `validate_completed_run`. Git snapshots must drop any status entry whose normalized path begins `.ai/icode/`:

```python
def _is_codex_control_status(line: str) -> bool:
    path = re.sub(r"^.. ", "", line).lstrip('"')
    return path == ".ai/icode" or path.startswith(".ai/icode/")
```

The target snapshot includes the target run directory files and resolved artifact map, but code/Git snapshots exclude all `.ai/icode/**`. `finish` marks `stale_input` only for filtered target, source, or Git changes.

- [ ] **Step 5: Port schemas and validate immutable outputs**

Copy the upstream manifest/round schemas unchanged except descriptions that name the Codex container. Keep verdict, severity, finding lifecycle, fresh-only `new` status, SHA-256 immutability, worklist declaration hashes, and complete-round reconstruction requirements.

- [ ] **Step 6: Run Python, shell, and simulation tests**

```bash
python3 -m pytest tests/test_crosscheck.py -q
bash tests/test_crosscheck_contract.sh
bash tests/test_crosscheck_demo_sim.sh
bash tools/selfcheck_crosscheck.sh
```

Expected: all PASS and no files outside `.ai/icode/.crosscheck/` change.

- [ ] **Step 7: Commit**

```bash
git add tools/icode_crosscheck.py tools/selfcheck_crosscheck.sh schemas/crosscheck-manifest.schema.json schemas/crosscheck-round.schema.json tests/test_crosscheck.py tests/test_crosscheck_contract.sh tests/test_crosscheck_demo_sim.sh
git commit -m "feat: add persistent Codex crosscheck reviews"
```

### Task 4: Add crosscheck workflow documentation and routing

**Files:**
- Create: `steps/crosscheck.md`
- Create: `references/crosscheck_mode.md`
- Create: `references/inspection_worklist.md`
- Modify: `SKILL.md`
- Modify: `steps/help.md`
- Modify: `tools/lint_codex_contract.py`
- Modify: `tests/test_codex_contract.py`

**Interfaces:**
- Consumes: controller CLI from Task 3.
- Produces: `$icodex crosscheck [--ticket ID | run path]` route.
- Preserves: `$icodex-review` as the separate zero-write external review path.

- [ ] **Step 1: Add failing route and boundary assertions**

Extend `tests/test_codex_contract.py` so the command set includes crosscheck and the linter routes it to `steps/crosscheck.md`:

```python
def test_crosscheck_is_persistent_but_target_read_only(self) -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    step = (ROOT / "steps/crosscheck.md").read_text(encoding="utf-8")
    self.assertIn("$icodex crosscheck", skill)
    self.assertIn(".ai/icode/.crosscheck/", step)
    self.assertIn("不得修改目标工单", step)
    self.assertIn("$icodex-review", skill)
```

- [ ] **Step 2: Run contract tests to prove RED**

Run: `python3 -m pytest tests/test_codex_contract.py -q`

Expected: FAIL because the route and files do not exist.

- [ ] **Step 3: Port and adapt crosscheck workflow references**

Port the three upstream Markdown files. Replace `/icode` with `$icodex`, `.icode_output/.crosscheck/.icode_output_N` with `.ai/icode/.crosscheck/icode_N`, and `icode_control.py resolve-ticket` with `icode_state.py resolve-ticket`. Keep fresh-before-history, worklist evidence, zero target write, multi-round recovery, stale-input, and explicit `$icodex patch` handoff rules.

- [ ] **Step 4: Register command and preserve external-review boundary**

Add `crosscheck` to the SKILL frontmatter description, staged auxiliary command list, command table, help output, and route map:

```python
COMMAND_ROUTES["crosscheck"] = "steps/crosscheck.md"
```

Document that crosscheck writes its isolated records while `$icodex-review` writes nothing and returns its report in the response.

- [ ] **Step 5: Run contract lint and commit**

```bash
python3 -m pytest tests/test_codex_contract.py -q
python3 tools/lint_codex_contract.py .
git add SKILL.md steps/help.md steps/crosscheck.md references/crosscheck_mode.md references/inspection_worklist.md tools/lint_codex_contract.py tests/test_codex_contract.py
git commit -m "docs: expose Codex crosscheck workflow"
```

Expected: PASS.

### Task 5: Restore `$icodex start` as the full staged chain

**Files:**
- Modify: `SKILL.md`
- Modify: `steps/run.md`
- Modify: `steps/01_plan.md`
- Modify: `steps/help.md`
- Modify: `steps/00_init.md`
- Modify: `steps/log.md`
- Modify: `steps/08_patch.md`
- Modify: `references/dir_and_metadata.md`
- Modify: `references/anti_laziness.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `tools/lint_codex_contract.py`
- Modify: `tests/test_codex_contract.py`

**Interfaces:**
- Produces: `start` and `run` both route to `steps/run.md` and resume/execute steps 1→6.
- Preserves: `plan` routes to `steps/01_plan.md` and stops after step 1; `fast` is unchanged.

- [ ] **Step 1: Add failing route parity assertions**

Add tests that reject every old start-as-plan statement in active docs and require route parity:

```python
def test_start_and_run_share_full_chain_route(self) -> None:
    self.assertEqual(COMMAND_ROUTES["start"], "steps/run.md")
    self.assertEqual(COMMAND_ROUTES["run"], "steps/run.md")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    self.assertIn("`$icodex start` 与 `$icodex run`", skill)
    self.assertNotIn("start` 永远只是 `$icodex plan`", skill)
```

Add a repository text assertion over the listed active files that fails on `start 是 plan`、`start.*plan 的兼容别名`、`start.*步骤1后停止`.

- [ ] **Step 2: Run contract tests to prove RED**

Run: `python3 -m pytest tests/test_codex_contract.py -q`

Expected: FAIL on the old route and documentation.

- [ ] **Step 3: Change the canonical route and orchestration wording**

Set both routes to `steps/run.md`; make the run step command line explicitly accept both names:

```markdown
**命令**：`$icodex start [需求]` / `$icodex run [需求]`

`start` 是上游一致的标准全流程入口，`run` 是 Codex 兼容别名；两者创建/复用同一工单并严格执行 01→06。`plan` 不路由到本文件。
```

Every transition retains `icode_state.py validate`, artifact existence, status, `code_files`, L1 stopping, and resume-from-`completed_steps` behavior.

- [ ] **Step 4: Update all user-facing entry and recovery text**

Change init/log/patch prompts, history-injection command lists, workload recommendations, README command tables, and examples so full-chain recommendations prefer `start` and may mention `run` as an alias. Keep all plan-only examples on `$icodex plan`; do not replace `plan` with start.

- [ ] **Step 5: Update linter invariants and verify no stale semantics remain**

Replace the old literal checks with:

```python
if COMMAND_ROUTES["start"] != COMMAND_ROUTES["run"]:
    errors.append("start and run must share steps/run.md")
if "`$icodex plan` 只执行步骤 1" not in skill:
    errors.append("plan must remain the single-step entry")
```

Run:

```bash
python3 -m pytest tests/test_codex_contract.py -q
python3 tools/lint_codex_contract.py .
rg -n 'start.*plan.*(别名|暂停)|start.*步骤1后停止' SKILL.md README*.md steps references
```

Expected: tests/lint PASS; `rg` returns no stale start-as-plan statements.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md README.md README.zh-CN.md steps/run.md steps/01_plan.md steps/help.md steps/00_init.md steps/log.md steps/08_patch.md references/dir_and_metadata.md references/anti_laziness.md tools/lint_codex_contract.py tests/test_codex_contract.py
git commit -m "feat: restore start as the full staged workflow"
```

### Task 6: Full regression, boundary audit, and handoff

**Files:**
- Modify only files required to fix failures introduced by Tasks 1–5.
- Verify: entire repository and both design/plan documents.

**Interfaces:**
- Consumes: all preceding task outputs.
- Produces: verified `codex` branch ready for final review and push.

- [ ] **Step 1: Run the complete Python suite**

Run: `python3 -m pytest tests -q`

Expected: PASS.

- [ ] **Step 2: Run shell contract and selfcheck suites**

```bash
bash tests/test_schema_migration.sh
bash tests/test_inspection_worklist_contract.sh
bash tests/test_crosscheck_contract.sh
bash tests/test_crosscheck_demo_sim.sh
bash tools/selfcheck_inspection_worklist.sh
bash tools/selfcheck_crosscheck.sh
```

Expected: all PASS.

- [ ] **Step 3: Run static boundary checks**

```bash
python3 tools/lint_codex_contract.py .
git diff --check origin/codex...HEAD
rg -n '/icode|\.icode_output|~/\.claude' SKILL.md README*.md steps references tools/icode_crosscheck.py tools/inspection_worklist.py
```

Expected: lint and diff check PASS. Every remaining legacy marker is same-line documented as read-only or occurs only in a deliberate exclusion test.

- [ ] **Step 4: Verify write isolation with before/after digests**

Run the crosscheck fixture simulation, record a digest of the target run and source tree excluding `.ai/icode/.crosscheck`, complete two rounds, and assert the digest is unchanged. Confirm only the crosscheck container contains new files and it contains no `.ico_metadata.json`.

- [ ] **Step 5: Inspect final status and commits**

```bash
git status --short --branch
git log --oneline origin/codex..HEAD
git diff --stat origin/codex...HEAD
```

Expected: clean worktree; commits contain only the approved spec, plan, resolver, crosscheck, routing, docs, and tests.

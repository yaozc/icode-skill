import shutil
import tempfile
import unittest
from pathlib import Path

from tools.lint_codex_contract import (
    COMMAND_ROUTES,
    MCP_THREE_STATE_TRUTH_SOURCES,
    PUBLIC_LIBRARY_CLAUSES,
    PUBLIC_LIBRARY_HOOK,
    lint_active_boundaries,
    lint_fast_risk_contract,
    lint_workflow_contract,
    lint_mcp_fallback_contract,
    lint_public_library_contract,
    lint_repo,
)


class BoundaryTests(unittest.TestCase):
    def make_root(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "steps").mkdir()
        (root / "mcp" / "demo").mkdir(parents=True)
        return temporary, root

    def test_active_claude_write_path_fails(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "steps" / "bad.md").write_text("write ~/.claude/config now\n", encoding="utf-8")
        self.assertTrue(lint_active_boundaries(root))

    def test_read_only_compatibility_line_passes(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "steps" / "ok.md").write_text("legacy read-only: ~/.claude/icode_data\n", encoding="utf-8")
        self.assertEqual(lint_active_boundaries(root), [])

    def test_legacy_allowlisted_installer_passes(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "mcp" / "demo" / "install.sh").write_text("write ~/.claude.json\n", encoding="utf-8")
        self.assertEqual(lint_active_boundaries(root), [])

    def test_active_legacy_installer_link_fails(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "steps" / "bad.md").write_text("run mcp/demo/install.sh\n", encoding="utf-8")
        self.assertTrue(lint_active_boundaries(root))

    def test_host_specific_mcp_fallback_fails(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        for relative in MCP_THREE_STATE_TRUTH_SOURCES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("unavailable_before_call\n", encoding="utf-8")
        (root / "SKILL.md").write_text(
            'unavailable_before_call\nAgent(model="haiku")\n',
            encoding="utf-8",
        )
        self.assertTrue(lint_mcp_fallback_contract(root))


class RepositoryContractTests(unittest.TestCase):
    def test_public_library_evidence_layers_and_conditional_applicability(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(lint_public_library_contract(root), [])

    def test_public_library_profile_cannot_be_weakened_or_hidden(self) -> None:
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = Path(__file__).resolve().parents[1]
            surfaces = ("references/domain-checklists.md", "steps/02_review.md",
                        "steps/05_deepcheck.md", "steps/06_audit.md")
            for relative in surfaces:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repository / relative, path)
            self.assertEqual(lint_public_library_contract(root), [])
            profile = root / surfaces[0]
            original = profile.read_text(encoding="utf-8")
            for clause in PUBLIC_LIBRARY_CLAUSES:
                for replacement in ("", f"<!-- {clause} -->", f"```text\n{clause}\n```",
                                    "Headers or a rebuilt consumer alone prove every compatibility layer."):
                    with self.subTest(clause=clause, replacement=replacement):
                        profile.write_text(original.replace(clause, replacement), encoding="utf-8")
                        self.assertTrue(lint_public_library_contract(root))
            profile.write_text(original, encoding="utf-8")
            for relative in surfaces[1:]:
                path = root / relative
                original_step = path.read_text(encoding="utf-8")
                path.write_text(original_step.replace(PUBLIC_LIBRARY_HOOK, "unrelated.md"), encoding="utf-8")
                self.assertTrue(any(relative in error for error in lint_public_library_contract(root)))
                path.write_text(original_step, encoding="utf-8")

    def test_workflow_hook_cannot_disappear_from_patch(self) -> None:
        import shutil
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        repository = Path(__file__).resolve().parents[1]
        for relative in ("SKILL.md", "references/codex_runtime.md", "references/dir_and_metadata.md",
                         "references/workflow_contract.md", "steps/verify.md", "steps/fast.md", "steps/01_plan.md",
                         "steps/02_review.md", "steps/03_merge.md", "steps/04_code.md", "steps/05_deepcheck.md",
                         "steps/06_audit.md", "steps/08_patch.md", "steps/status.md"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / relative, path)
        self.assertEqual(lint_workflow_contract(root), [])
        path = root / "steps/08_patch.md"
        path.write_text(path.read_text().replace("workflow-plan", "old-dispatch"))
        self.assertTrue(lint_workflow_contract(root))

    def test_risk_hook_cannot_disappear_from_a_downstream_step(self) -> None:
        import shutil
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        repository = Path(__file__).resolve().parents[1]
        for relative in ("SKILL.md", "steps/fast.md", "steps/01_plan.md", "steps/02_review.md",
                         "steps/03_merge.md", "steps/04_code.md", "steps/05_deepcheck.md", "steps/06_audit.md",
                         "references/dir_and_metadata.md", "references/codex_runtime.md", "references/fast_risk.md"):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / relative, destination)
        self.assertEqual(lint_fast_risk_contract(root), [])
        deepcheck = root / "steps/05_deepcheck.md"
        deepcheck.write_text(deepcheck.read_text().replace("workflow-plan", "missing-hook"))
        errors = lint_fast_risk_contract(root)
        self.assertTrue(any("steps/05_deepcheck.md" in error for error in errors))

    def test_mcp_fallback_contract_is_host_neutral_and_three_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(lint_mcp_fallback_contract(root), [])

    def test_start_is_the_only_full_chain_route(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        plan_step = (root / "steps" / "01_plan.md").read_text(encoding="utf-8")
        directory_rules = (root / "references" / "dir_and_metadata.md").read_text(encoding="utf-8")
        self.assertEqual(COMMAND_ROUTES["start"], "steps/01_plan.md")
        self.assertNotIn("run", COMMAND_ROUTES)
        self.assertEqual(COMMAND_ROUTES["plan"], "steps/01_plan.md")
        self.assertFalse((root / "steps" / "run.md").exists())
        self.assertIn("`$icodex start` 是唯一标准全流程入口", skill)
        self.assertIn("`$icodex plan` 只执行步骤 1 后暂停", skill)
        self.assertNotIn("$icodex run", skill)
        self.assertIn("无参数时恢复最新未完成", skill)
        self.assertIn("单独调用 `plan` 随后停止", plan_step)
        self.assertIn("~/.codex/skills/icodex/tools/icode_state.py validate", plan_step)
        self.assertNotIn("python3 tools/icode_state.py validate", plan_step)
        self.assertIn("统一分派规则", plan_step)
        self.assertNotIn("立即继续执行步骤2", plan_step)
        self.assertIn("COMMAND=start|plan", directory_rules)
        self.assertIn("HAS_REQUIREMENT=1", directory_rules)
        self.assertIn("REUSE=1", directory_rules)
        resume_binding = 'if [ "$REUSE" = "1" ]; then\n  ICODE_OUT_DIR="$CAND"\nfi'
        self.assertIn(resume_binding, skill)
        self.assertIn(resume_binding, directory_rules)
        self.assertIn('if [ "$HAS_REQUIREMENT" = "0" ]; then', directory_rules)
        self.assertIn("无参数不得创建新目录", directory_rules)

    def test_crosscheck_is_persistent_but_target_read_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        step = (root / "steps" / "crosscheck.md").read_text(encoding="utf-8")
        self.assertEqual(COMMAND_ROUTES["crosscheck"], "steps/crosscheck.md")
        self.assertIn("$icodex crosscheck", skill)
        self.assertIn(".ai/icode/.crosscheck/", step)
        self.assertIn("不得修改目标工单", step)
        self.assertIn("$icodex-review", skill)

    def test_repository_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(lint_repo(root), [])


class StaticReadAndExecutionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        repository = Path(__file__).resolve().parents[1]
        # mutation 永不写共享工作区，并保留链接目标以免产生无关 lint 错误。
        shutil.copytree(
            repository, self.root, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", ".ai", ".codegraph", "__pycache__",
                                         ".pytest_cache", "node_modules", ".venv"),
        )
        self.assertEqual(lint_repo(self.root), [])

    def assert_mutation_rejected(self, relative: str, original: str, mutated: str) -> None:
        path = self.root / relative
        path.write_text(mutated, encoding="utf-8")
        try:
            self.assertTrue(
                any(relative in error for error in lint_repo(self.root)),
                f"undetected contract mutation: {relative}",
            )
        finally:
            path.write_text(original, encoding="utf-8")

    def test_static_read_truth_source_requires_all_cache_boundaries(self) -> None:
        relative = "references/thinking_core.md"
        path = self.root / relative
        original = path.read_text(encoding="utf-8")
        for clause in (
            "首次必须完整实读静态 references 正文并计算 SHA256。",
            "仅当绝对 skill 根、文件路径、SHA256 均一致，且完整正文仍在当前上下文时，才可复用。",
            "上下文压缩、正文丢失、切换 skill 根或内容变化时，必须重新完整实读并计算 SHA256。",
            "SHA256 只证明字节身份，不证明已实读；摘要、确认行和文件哈希不能替代完整正文。",
            "确认行必须区分实际实读与复用，并列出绝对 skill 根、文件路径和 SHA256。",
            "业务源码实读、每轮判断和 Read/worklist 登记不得复用。",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, original)
                for replacement in ("", f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                    self.assert_mutation_rejected(
                        relative, original, original.replace(clause, "") + "\n" + replacement + "\n",
                    )

    def test_unconditional_static_reread_cannot_return_on_any_surface(self) -> None:
        for relative in ("SKILL.md", "references/thinking_core.md", "references/thinking_detail.md",
                         "references/anti_laziness.md", "references/mcp_integration.md",
                         "references/workflow_contract.md", "steps/verify.md", "steps/06_audit.md"):
            original = (self.root / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assert_mutation_rejected(
                    relative, original,
                    original + "\n静态 references 每步必须重新 Read，同会话已读不豁免。\n",
                )

    def test_mcp_configuration_or_handshake_cannot_claim_session_availability(self) -> None:
        relative = "references/mcp_integration.md"
        original = (self.root / relative).read_text(encoding="utf-8")
        for claim in (
            "任一即视为已配置可用",
            "配置存在即可用",
            "安装完成即可调用",
            "握手成功即证明当前会话可用",
        ):
            with self.subTest(claim=claim):
                self.assert_mutation_rejected(relative, original, original + "\n" + claim + "\n")

    def test_static_read_hooks_cannot_disappear(self) -> None:
        hook = "thinking_core.md#静态-references-读取与复用合同"
        for relative in ("SKILL.md", "references/thinking_detail.md", "references/anti_laziness.md",
                         "references/mcp_integration.md", "references/workflow_contract.md",
                         "steps/verify.md", "steps/06_audit.md"):
            original = (self.root / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn(hook, original)
                self.assert_mutation_rejected(relative, original, original.replace(hook, "thinking_core.md"))

    def test_dedup_coverage_contract_requires_shared_rules(self) -> None:
        hook = "mcp_integration.md#语义去重覆盖规则"
        for relative in ("steps/02_review.md", "steps/05_deepcheck.md", "references/mcp_per_step.md"):
            original = (self.root / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assert_mutation_rejected(relative, original, original.replace(hook, "mcp_integration.md"))

        relative = "references/mcp_integration.md"
        original = (self.root / relative).read_text(encoding="utf-8")
        for clause in (
            "只有可信枚举才能判定低于阈值。",
            "枚举不完整或不可信时，记录未覆盖范围和原因，不能把未知计为零。",
            "工具不可用或调用失败时，记录实际核查范围和剩余覆盖缺口。",
            "仅当当前候选、范围与输入身份一致时复用目录或分类。",
        ):
            with self.subTest(clause=clause):
                self.assert_mutation_rejected(
                    relative, original, original.replace(clause, "") + f"\n<!-- {clause} -->\n",
                )

    def test_mcp_five_layers_and_three_states_cannot_be_deleted_or_hidden(self) -> None:
        relative = "references/mcp_integration.md"
        original = (self.root / relative).read_text(encoding="utf-8")
        for clause in ("| 源码 |", "| 安装 |", "| 注册 |", "| 握手 |", "| 当前会话可用 |",
                       "配置存在不等于当前会话可调用。",
                       "源码、安装、注册、握手和当前会话可用不能混淆，也不是五种执行状态。",
                       "called", "degraded_after_attempt", "unavailable_before_call", "attempted=false"):
            with self.subTest(clause=clause):
                self.assertIn(clause, original)
                for replacement in ("", f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                    self.assert_mutation_rejected(
                        relative, original, original.replace(clause, "") + "\n" + replacement + "\n",
                    )

    def test_execution_evidence_cannot_be_deleted_or_hidden(self) -> None:
        for relative in ("references/workflow_contract.md", "steps/verify.md", "steps/06_audit.md"):
            original = (self.root / relative).read_text(encoding="utf-8")
            for clause in (
                "实际流程步骤、verification_runs[].id 或供应方执行标识必须与原始日志逐项对账。",
                "每次新执行必须使用新的执行标识和独立证据路径，保留独立原始日志，不覆盖旧执行。",
                "HANDOFF 只定位上下文，不是原始观测，不能替代原始日志或实际执行证据。",
                "同 ID 原样重放只是幂等登记，不是新执行。",
                "这些是报告证据要求，不新增 schema 字段，也不追补旧票的命名要求。",
            ):
                with self.subTest(relative=relative, clause=clause):
                    self.assertIn(clause, original)
                    for replacement in ("", f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                        self.assert_mutation_rejected(
                            relative, original, original.replace(clause, "") + "\n" + replacement + "\n",
                        )

    def test_maintenance_readmes_keep_override_separate_from_mcp(self) -> None:
        for relative in ("README.md", "README.zh-CN.md"):
            original = (self.root / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("ICODEX_TEST_PYTHON_BIN", original)
                self.assert_mutation_rejected(
                    relative, original, original.replace("ICODEX_TEST_PYTHON_BIN", "ICODEX_MCP_PYTHON_BIN"),
                )

    def test_replay_handoff_and_reused_paths_cannot_claim_new_execution(self) -> None:
        for relative in ("references/workflow_contract.md", "steps/verify.md", "steps/06_audit.md"):
            original = (self.root / relative).read_text(encoding="utf-8")
            for claim in ("HANDOFF 可以作为原始观测", "同 ID 原样重放视为新执行", "新执行可复用旧证据路径"):
                with self.subTest(relative=relative, claim=claim):
                    self.assert_mutation_rejected(relative, original, original + "\n" + claim + "\n")


if __name__ == "__main__":
    unittest.main()

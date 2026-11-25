"""SKILL.md 是唯一撰写点；references/full_workflow.md 的速查段由工具生成，禁止手改。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/sync_shared_docs.py"

BEGIN = "<!-- BEGIN shared:artifact-vocabulary"
END = "<!-- END shared:artifact-vocabulary -->"


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=ROOT,
                          capture_output=True, text=True)


def test_mirror_is_in_sync_with_the_entry_document():
    result = run("--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_full_workflow_mirror_is_marked_as_generated():
    text = (ROOT / "references/full_workflow.md").read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1, "镜像段必须恰好有一对生成标记"
    assert text.count(END) == 1
    start, end = text.index(BEGIN), text.index(END)
    region = text[start:end]
    # 生成段内不得再出现第二份手写词表（lite 状态只允许来自 SKILL.md）。
    assert "lite_prepare_in_progress" in region
    assert "### 产物命名 + status 词表速查表" in region


def test_entry_document_stays_within_the_portable_size_budget():
    size = (ROOT / "SKILL.md").stat().st_size
    assert size <= 50 * 1024, f"SKILL.md {size} bytes exceeds the 51200-byte entry budget"

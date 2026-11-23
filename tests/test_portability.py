"""AC-7: the bundled scripts need nothing but a plain python3 (3.9+)."""
import ast
import sys

import pytest
from conftest import SCRIPT, SCRIPTS, run_cli

FILES = sorted(SCRIPTS.glob("*.py"))


def imported_top_levels(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names.add((node.module or "").split(".")[0])
    return names


@pytest.mark.skipif(sys.version_info < (3, 10), reason="sys.stdlib_module_names needs Python 3.10")
def test_only_standard_library_and_skill_modules_are_imported():
    local = {p.stem for p in FILES}
    for path in FILES:
        extra = imported_top_levels(path) - set(sys.stdlib_module_names) - local - {"__future__"}
        assert not extra, (path.name, extra)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_parses_as_python_3_9(path):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))


def test_runs_with_plain_python_and_prints_ucs2():
    proc = run_cli("count", "It’s ready")
    assert proc.returncode == 0 and "UCS-2" in proc.stdout


def test_entry_script_answers_help():
    assert run_cli("--help").returncode == 0
    assert SCRIPT.is_file()


def test_no_network_or_process_modules_are_used():
    banned = {"socket", "urllib", "http", "subprocess", "ssl", "requests"}
    for path in FILES:
        assert not (imported_top_levels(path) & banned), path.name

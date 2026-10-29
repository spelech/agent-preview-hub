#!/usr/bin/env python3
"""Gate 1: Verify release version sync, module LOC bounds (<=500), and Anti-Test-Theatre rules."""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).parent.resolve()


def main() -> int:
    errors = []

    # 1. Check SemVer sync between pyproject.toml and __init__.py
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_py = (ROOT / "src" / "agent_preview_hub" / "__init__.py").read_text(encoding="utf-8")

    m_toml = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    m_init = re.search(r'^__version__\s*=\s*"([^"]+)"', init_py, re.M)
    if not m_toml or not m_init or m_toml.group(1) != m_init.group(1):
        errors.append("Version mismatch between pyproject.toml and __init__.py")

    # 2. Enforce <= 500 LOC per source file and ban junk-drawer filenames
    banned_suffixes = ("manager.py", "helper.py", "util.py", "utils.py", "data.py")
    for py_file in (ROOT / "src" / "agent_preview_hub").rglob("*.py"):
        if py_file.name.lower().endswith(banned_suffixes):
            errors.append(f"Banned junk-drawer module name: {py_file.name}")
        line_count = len(py_file.read_text(encoding="utf-8").splitlines())
        if line_count > 500:
            errors.append(f"Module {py_file.name} exceeds 500 LOC ({line_count} lines)")

    # 3. Anti-Test-Theatre static check: forbid unittest.mock domain patching in tests/
    for test_file in (ROOT / "tests").rglob("test_*.py"):
        content = test_file.read_text(encoding="utf-8")
        if "unittest.mock" in content or "@patch(" in content:
            errors.append(f"Anti-Test-Theatre violation in {test_file.name}: unittest.mock is prohibited")

    if errors:
        for err in errors:
            sys.stderr.write(f"❌ {err}\n")
        return 1

    print("✅ Gate 1 passed: SemVer synced, all modules <= 500 LOC, zero Anti-Test-Theatre violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

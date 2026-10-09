#!/usr/bin/env python3
"""
fix_auth_imports_v2.py

Targeted fix for files where the auth import was injected at an indented
scope (inside a function body) rather than at module level.

Strategy:
1. Remove ALL occurrences of the auth import line from the file.
2. Re-insert it at the correct module-level position (after the last
   module-level import block, before any class/def/blank-then-code sections).
"""
import re
import sys
from pathlib import Path

ROUTES_DIR = Path(__file__).parent.parent / "services/api/app/api/routes"
AUTH_IMPORT = "from app.core.auth import get_current_user"

TARGET_FILES = [
    "compliance_integration.py",
    "compliance_scorecard.py",
    "clients.py",
    "dlq_management.py",
    "ace_import.py",
    "entries.py",
]


def find_module_level_import_end(lines: list[str]) -> int:
    """
    Find the index of the last module-level import line.
    Module-level imports are at indent=0 and not inside a parenthesised import.
    """
    inside_paren = 0
    last_import_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track parenthesis depth for multi-line imports
        if stripped.startswith(("from ", "import ")) and "(" in stripped:
            inside_paren += stripped.count("(") - stripped.count(")")
            last_import_idx = i
            continue
        if inside_paren > 0:
            inside_paren += stripped.count("(") - stripped.count(")")
            if inside_paren <= 0:
                inside_paren = 0
                last_import_idx = i
            continue

        # Module-level (no indent) import
        if line and not line[0].isspace() and stripped.startswith(("from ", "import ")):
            last_import_idx = i

        # Stop at first def/class at module level (unindented)
        if line and not line[0].isspace() and stripped.startswith(("def ", "class ", "@")):
            break

    return last_import_idx


def fix_file(filepath: Path) -> bool:
    content = filepath.read_text(encoding="utf-8")

    if AUTH_IMPORT not in content:
        return False

    # Count how many times it appears
    occurrences = content.count(AUTH_IMPORT)

    # Remove all occurrences
    lines = content.splitlines(keepends=True)
    cleaned = [l for l in lines if l.strip() != AUTH_IMPORT]

    # Re-insert at correct module-level position
    insert_after = find_module_level_import_end(cleaned)
    cleaned.insert(insert_after + 1, AUTH_IMPORT + "\n")

    new_content = "".join(cleaned)
    filepath.write_text(new_content, encoding="utf-8")
    print(f"  🔧 Fixed ({occurrences}→1 import): {filepath.name}")
    return True


def main():
    fixed = 0
    for name in TARGET_FILES:
        filepath = ROUTES_DIR / name
        if not filepath.exists():
            # Try admin subdirectory
            filepath = ROUTES_DIR / "admin" / name
        if not filepath.exists():
            print(f"  ⚠️  Not found: {name}")
            continue
        if fix_file(filepath):
            fixed += 1

    print(f"\nFixed {fixed} files.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
fix_auth_imports.py — Fixes malformed get_current_user imports.

The previous script incorrectly inserted the import line inside a
multi-line `from X import (` block. This script detects and fixes those.
"""
import re
import sys
from pathlib import Path

ROUTES_DIR = Path(__file__).parent.parent / "services/api/app/api/routes"
AUTH_IMPORT = "from app.core.auth import get_current_user"


def fix_file(filepath: Path) -> bool:
    content = filepath.read_text(encoding="utf-8")

    # Pattern: auth import was inserted INSIDE a multi-line import block
    # e.g. from app.schemas.alerts import (\nfrom app.core.auth import get_current_user\n    Foo,\n)
    broken_pattern = re.compile(
        r'(from\s+\S+\s+import\s+\()\n'  # opening of a multi-line import
        r'(from app\.core\.auth import get_current_user\n)'  # wrongly inserted line
    )

    if not broken_pattern.search(content):
        return False

    # Move the auth import to before the multi-line import block it got embedded in.
    # Strategy: remove it from inside, then ensure it's added at the right place.

    # Remove all instances of the wrongly embedded auth import
    content = re.sub(
        r'(from\s+\S+\s+import\s+\()\n(from app\.core\.auth import get_current_user\n)',
        r'\1\n',
        content,
    )

    # Now ensure the auth import is present at the top-level import section.
    if AUTH_IMPORT not in content:
        # Insert after the last top-level import line (not inside a parenthesised block)
        lines = content.splitlines(keepends=True)
        inside_paren = False
        last_import_line = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "(" in stripped and (stripped.startswith("from ") or stripped.startswith("import ")):
                inside_paren = True
            if inside_paren and ")" in stripped:
                inside_paren = False
                last_import_line = i
                continue
            if not inside_paren and (stripped.startswith("from ") or stripped.startswith("import ")):
                last_import_line = i

        lines.insert(last_import_line + 1, AUTH_IMPORT + "\n")
        content = "".join(lines)

    filepath.write_text(content, encoding="utf-8")
    return True


def main():
    errors = []
    fixed = []
    for filepath in sorted(ROUTES_DIR.rglob("*.py")):
        if "__pycache__" in str(filepath):
            continue
        try:
            if fix_file(filepath):
                fixed.append(filepath.name)
                print(f"  🔧 Fixed: {filepath.name}")
        except Exception as e:
            errors.append(f"  ❌ ERROR in {filepath.name}: {e}")

    print(f"\nFixed {len(fixed)} files.")
    for e in errors:
        print(e)


if __name__ == "__main__":
    main()

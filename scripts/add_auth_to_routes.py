#!/usr/bin/env python3
"""
add_auth_to_routes.py

Patches all GATE API route files that don't already have authentication
by adding a router-level dependency on get_current_user.

Strategy:
  - Locate every `router = APIRouter(...)` definition in the file.
  - If the router already has `get_current_user` / `require_role` /
    `require_admin` wired in, skip the file.
  - Otherwise:
    1. Add the import for get_current_user if not present.
    2. Add `dependencies=[Depends(get_current_user)]` to the APIRouter() call.

Public routes (intentionally unauthenticated):
  - leads.py             — marketing lead capture from landing page
  - landing_analytics.py — public page-view tracking
  - storage_callbacks.py — webhook callbacks from storage provider (secret token
                           based, not session based)

Admin-only routes (already have admin_required or equivalent):
  - admin/retry_dlq.py
  - admin/file_type_mapping.py
  - client_portal.py     — handles login itself

Run from project root:
  python scripts/add_auth_to_routes.py
"""
import re
import sys
from pathlib import Path

ROUTES_DIR = Path(__file__).parent.parent / "services/api/app/api/routes"

# These files are intentionally public (no session auth needed) or already handled.
SKIP_FILES = {
    "leads.py",               # Public lead capture
    "landing_analytics.py",   # Public analytics
    "storage_callbacks.py",   # Storage webhook — uses HMAC secret, not session
    "client_portal.py",       # Handles login/register itself
    "__init__.py",
}

AUTH_IMPORT = "from app.core.auth import get_current_user"
DEPENDS_IMPORT = "from fastapi import"
ROUTER_PATTERN = re.compile(
    r'(router\s*=\s*APIRouter\s*\()(.*?)(\))',
    re.DOTALL,
)
ALREADY_HAS_AUTH_PATTERNS = [
    "get_current_user",
    "require_role",
    "require_admin",
    "admin_required",
]


def file_needs_patching(content: str) -> bool:
    return not any(p in content for p in ALREADY_HAS_AUTH_PATTERNS)


def ensure_imports(content: str) -> str:
    """Ensure get_current_user is imported."""
    if AUTH_IMPORT in content:
        return content

    # Add after the last `from app.*` or `from fastapi` import block
    # Find a good insertion point: after the first block of imports
    lines = content.splitlines(keepends=True)
    insert_after = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_after = i

    lines.insert(insert_after + 1, AUTH_IMPORT + "\n")
    return "".join(lines)


def ensure_depends_import(content: str) -> str:
    """Ensure Depends is part of the fastapi imports."""
    # Find `from fastapi import ...` line(s)
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip().startswith("from fastapi import"):
            if "Depends" not in line:
                # Add Depends to the import
                lines[i] = line.rstrip().rstrip(",").rstrip() + ", Depends\n"
            return "".join(lines)
    return content


def patch_router(content: str, filepath: Path) -> str:
    """Add dependencies=[Depends(get_current_user)] to APIRouter()."""

    def _patch_match(m: re.Match) -> str:
        prefix = m.group(1)   # 'router = APIRouter('
        args = m.group(2)     # existing args
        suffix = m.group(3)   # ')'

        # Already has dependencies= ?
        if "dependencies=" in args:
            # Append get_current_user to existing list
            if "get_current_user" in args:
                return m.group(0)  # Nothing to do
            # Insert into the existing list
            args = re.sub(
                r'(dependencies\s*=\s*\[)',
                r'\1Depends(get_current_user), ',
                args,
            )
        else:
            # Add new dependencies kwarg
            sep = ",\n    " if "\n" in args else ", "
            args = args.rstrip() + f"{sep}dependencies=[Depends(get_current_user)]"

        return f"{prefix}{args}{suffix}"

    new_content = ROUTER_PATTERN.sub(_patch_match, content)
    if new_content == content:
        print(f"  ⚠️  No router= APIRouter(...) found in {filepath.name} — skipped")
    return new_content


def process_file(filepath: Path) -> bool:
    """Process a single route file. Returns True if modified."""
    content = filepath.read_text(encoding="utf-8")

    if not file_needs_patching(content):
        print(f"  ✓ Already has auth: {filepath.name}")
        return False

    original = content
    content = ensure_imports(content)
    content = ensure_depends_import(content)
    content = patch_router(content, filepath)

    if content == original:
        print(f"  - No changes needed: {filepath.name}")
        return False

    filepath.write_text(content, encoding="utf-8")
    print(f"  ✅ Patched: {filepath.name}")
    return True


def main():
    if not ROUTES_DIR.exists():
        print(f"ERROR: Routes dir not found: {ROUTES_DIR}")
        sys.exit(1)

    route_files = list(ROUTES_DIR.rglob("*.py"))
    modified = 0
    skipped = 0

    for filepath in sorted(route_files):
        if filepath.name in SKIP_FILES:
            print(f"  ⏭️  Public/special route (intentionally skipped): {filepath.name}")
            skipped += 1
            continue
        if "__pycache__" in str(filepath):
            continue
        if process_file(filepath):
            modified += 1

    print(f"\n{'='*60}")
    print(f"Done. {modified} files patched, {skipped} intentionally skipped.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

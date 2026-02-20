#!/usr/bin/env bash
#
# promote.sh — Automate branch promotions for dev → qa → main
#
# Usage:
#   ./scripts/promote.sh dev-to-qa    Merge dev into qa, stripping dev-only files
#   ./scripts/promote.sh qa-to-main   Merge qa into main, stripping qa-only files
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*"; }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
require_clean_tree() {
    if ! git diff --quiet || ! git diff --cached --quiet; then
        die "Working tree is dirty. Commit or stash changes first."
    fi
}

read_exclude_file() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        die "Exclude file not found: $file"
    fi
    # Return non-empty, non-comment lines
    grep -v '^\s*#' "$file" | grep -v '^\s*$' || true
}

strip_paths() {
    # Remove listed paths from the current working tree and stage the deletions.
    local exclude_file="$1"
    local removed=0

    while IFS= read -r pattern; do
        # Expand pattern — could be a file or directory
        if [[ -e "$REPO_ROOT/$pattern" ]]; then
            info "  Removing: $pattern"
            git rm -rf --quiet "$pattern"
            ((removed++)) || true
        fi
    done < <(read_exclude_file "$exclude_file")

    echo "  ($removed path(s) removed)"
}

# ---------------------------------------------------------------------------
# Promotion: dev → qa
# ---------------------------------------------------------------------------
promote_dev_to_qa() {
    local exclude_file="$REPO_ROOT/.branch-exclude-qa"
    local source="dev"
    local target="qa"

    require_clean_tree

    info "Promoting $source → $target"

    # Switch to target branch
    git checkout "$target"

    # Merge source into target
    info "Merging $source into $target..."
    if ! git merge "$source" --no-edit; then
        die "Merge conflicts detected. Resolve manually, then run: git commit"
    fi

    # Strip dev-only files
    info "Stripping dev-only files..."
    strip_paths "$exclude_file"

    # Commit the removals (if any files were actually removed)
    if ! git diff --cached --quiet; then
        git commit -m "Strip dev-only files from qa after merge from $source"
    else
        info "No dev-only files to strip."
    fi

    info "Done. $target is ready."
    info "Review with: git log --oneline -5 $target"
    info "To go back:  git checkout $source"

    # Return to source branch
    git checkout "$source"
}

# ---------------------------------------------------------------------------
# Promotion: qa → main
# ---------------------------------------------------------------------------
promote_qa_to_main() {
    local exclude_file="$REPO_ROOT/.branch-exclude-main"
    local source="qa"
    local target="main"

    require_clean_tree

    info "Promoting $source → $target"

    # Switch to target branch
    git checkout "$target"

    # Merge source into target
    info "Merging $source into $target..."
    if ! git merge "$source" --no-edit; then
        die "Merge conflicts detected. Resolve manually, then run: git commit"
    fi

    # Strip qa-only files (if any)
    info "Stripping qa-only files..."
    strip_paths "$exclude_file"

    if ! git diff --cached --quiet; then
        git commit -m "Strip qa-only files from main after merge from $source"
    else
        info "No qa-only files to strip."
    fi

    info "Done. $target is ready."
    info "Review with: git log --oneline -5 $target"
    info "To go back:  git checkout $source"

    # Return to source branch
    git checkout "$source"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-}" in
    dev-to-qa)
        promote_dev_to_qa
        ;;
    qa-to-main)
        promote_qa_to_main
        ;;
    *)
        echo "Usage: $0 {dev-to-qa|qa-to-main}"
        echo ""
        echo "  dev-to-qa   Merge dev into qa, strip dev-only files"
        echo "  qa-to-main  Merge qa into main, strip qa-only files"
        exit 1
        ;;
esac

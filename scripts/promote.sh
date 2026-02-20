#!/usr/bin/env bash
#
# promote.sh — Automate branch promotions for dev → qa → main → external
#
# Usage:
#   ./scripts/promote.sh dev-to-qa    Merge dev into qa, stripping dev-only files
#   ./scripts/promote.sh qa-to-main   Merge qa into main, stripping qa-only files
#   ./scripts/promote.sh publish      Push main to external-oaa-magento
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
            git rm -rf --quiet "$pattern" 2>/dev/null || true
            ((removed++)) || true
        else
            info "  Skipping (not found): $pattern"
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
# Publish: main → external repo
# ---------------------------------------------------------------------------
publish() {
    local remote="external"
    local source_repo="jifflee/source-oaa-magento"
    local external_repo="jifflee/external-oaa-magento"

    require_clean_tree

    info "Publishing main → $remote (external-oaa-magento)"

    # Verify the remote exists
    if ! git remote get-url "$remote" > /dev/null 2>&1; then
        die "Remote '$remote' not configured. Run: git remote add external <url>"
    fi

    # Push main to external
    git push "$remote" main

    # Sync repo description and topics from source
    info "Syncing repo metadata..."
    local desc
    desc=$(gh repo view "$source_repo" --json description -q '.description')
    gh repo edit "$external_repo" --description "$desc" 2>/dev/null || true

    local topics
    topics=$(gh repo view "$source_repo" --json repositoryTopics -q '.repositoryTopics[].name')
    for topic in $topics; do
        gh repo edit "$external_repo" --add-topic "$topic" 2>/dev/null || true
    done

    # Sync release if VERSION tag doesn't exist on external
    local version
    version=$(cat "$REPO_ROOT/VERSION" | tr -d '[:space:]')
    if ! gh release view "v${version}" --repo "$external_repo" > /dev/null 2>&1; then
        info "Creating release v${version} on external..."
        local body
        body=$(gh release view "v${version}" --repo "$source_repo" --json body -q '.body' 2>/dev/null || echo "Release v${version}")
        gh release create "v${version}" --repo "$external_repo" \
            --title "v${version}" \
            --notes "$body"
    else
        info "Release v${version} already exists on external."
    fi

    info "Done. main + metadata synced to $external_repo"
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
    publish)
        publish
        ;;
    *)
        echo "Usage: $0 {dev-to-qa|qa-to-main|publish}"
        echo ""
        echo "  dev-to-qa   Merge dev into qa, strip dev-only files"
        echo "  qa-to-main  Merge qa into main, strip qa-only files"
        echo "  publish     Push main to external-oaa-magento"
        exit 1
        ;;
esac

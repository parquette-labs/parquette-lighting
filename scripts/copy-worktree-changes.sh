#!/usr/bin/env bash
#
# Copy uncommitted and committed changes from a Claude Code worktree
# into the main working tree, without requiring a git commit.
#
# Usage:
#   From a worktree:  ./scripts/copy-worktree-changes.sh
#   From anywhere:    ./scripts/copy-worktree-changes.sh /path/to/worktree

set -euo pipefail

worktree_dir="${1:-.}"
worktree_dir="$(cd "$worktree_dir" && pwd)"

# Verify the given directory is a git worktree (not the main tree)
if ! git -C "$worktree_dir" rev-parse --git-dir >/dev/null 2>&1; then
    echo "Error: $worktree_dir is not a git repository" >&2
    exit 1
fi

main_dir="$(git -C "$worktree_dir" worktree list --porcelain | head -1 | sed 's/^worktree //')"
if [ "$main_dir" = "$worktree_dir" ]; then
    echo "Error: $worktree_dir is the main working tree, not a worktree" >&2
    exit 1
fi

# Find the merge base between the worktree branch and HEAD of main
worktree_head="$(git -C "$worktree_dir" rev-parse HEAD)"
main_head="$(git -C "$main_dir" rev-parse HEAD)"
merge_base="$(git -C "$worktree_dir" merge-base "$worktree_head" "$main_head")"

# Build a combined diff: committed changes since the merge base + any
# uncommitted changes in the worktree
diff_output="$(git -C "$worktree_dir" diff "$merge_base" HEAD; git -C "$worktree_dir" diff HEAD)"

if [ -z "$diff_output" ]; then
    echo "No changes to copy from worktree"
    exit 0
fi

echo "Changes from worktree ($worktree_dir):"
echo "$diff_output" | diffstat 2>/dev/null || echo "$diff_output" | grep '^diff --git' | sed 's/^diff --git a\//  /' | sed 's/ b\/.*//'
echo ""

# Check if the main working tree is clean
main_status="$(git -C "$main_dir" status --porcelain)"
if [ -z "$main_status" ]; then
    echo "Main working tree is clean. Applying changes..."
    echo "$diff_output" | git -C "$main_dir" apply -
    echo "Done. Changes applied to $main_dir"
    exit 0
fi

echo "Main working tree has uncommitted changes:"
git -C "$main_dir" status --short
echo ""

# Check for conflicts with a dry run
if echo "$diff_output" | git -C "$main_dir" apply --check 2>/dev/null; then
    echo "No conflicts detected."
    read -rp "Apply changes to main working tree? [y/N] " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        echo "$diff_output" | git -C "$main_dir" apply -
        echo "Done. Changes applied to $main_dir"
    else
        echo "Aborted."
    fi
else
    echo "Error: Conflicts detected. Cannot apply changes cleanly." >&2
    echo "Conflicting files:" >&2
    echo "$diff_output" | git -C "$main_dir" apply --check 2>&1 | head -20 >&2
    exit 1
fi

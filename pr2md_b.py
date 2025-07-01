#!/usr/bin/env python3
"""
Git Branch Changes Analyzer

A tool for generating comprehensive markdown reports of git branch changes with full diffs.
Designed for PR reviews and documentation, it intelligently handles different file types
and provides clean, readable output.

Features:
- Auto-detects merge base with common branches (main, master, develop)
- Shows complete file content for new files (without diff markers)
- Shows proper unified diffs for modified files with context
- Skips large unchanged sections in diffs to focus on actual changes
- Automatically detects and skips binary files
- Intelligently handles lockfiles and auto-generated files
- Groups changes by directory for better organization
- Provides comprehensive statistics and summaries
- Supports syntax highlighting for 25+ programming languages

Usage Examples:
    # Auto-detect base branch and generate changes.md
    python analyze_branch.py

    # Compare with specific branch
    python analyze_branch.py --base main

    # Compare with specific commit
    python analyze_branch.py --base-commit abc123

    # Specify custom output file
    python analyze_branch.py --base main --output my_changes.md

Output Structure:
- Summary with file counts and line statistics
- Changes grouped by directory
- Full file content for new files (clean, no + markers)
- Unified diffs for modified files with proper context
- Skipped sections for large unchanged areas
- Auto-generated files summarized (not shown in full)

Supported File Types:
- Source code: Python, JavaScript, TypeScript, Java, C/C++, Rust, Go, etc.
- Config files: JSON, YAML, TOML, XML, etc.
- Documentation: Markdown, HTML, CSS, etc.
- Auto-detected lockfiles: uv.lock, package-lock.json, yarn.lock, etc.

Requirements:
- Git repository
- Python 3.11+ (uses asyncio.TaskGroup syntax)
- Git command available in PATH
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_git_command(cmd: list[str]) -> tuple[str, int]:
    """Run a git command and return output and exit code."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        print(f"Error running git command: {e}")
        return "", 1


def get_merge_base(branch: str) -> str | None:
    """Get the merge base between current HEAD and the specified branch."""
    output, code = run_git_command(["git", "merge-base", "HEAD", branch])
    if code == 0 and output:
        return output
    return None


def get_commit_hash(ref: str) -> str | None:
    """Get the full commit hash for a reference."""
    output, code = run_git_command(["git", "rev-parse", ref])
    if code == 0 and output:
        return output
    return None


def get_current_branch() -> str:
    """Get the current branch name."""
    output, code = run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if code == 0 and output != "HEAD":
        return output

    # Fallback for detached HEAD
    output, code = run_git_command(["git", "describe", "--tags", "--exact-match"])
    if code == 0:
        return f"tag:{output}"

    # Last fallback - just use commit hash
    output, code = run_git_command(["git", "rev-parse", "--short", "HEAD"])
    return f"commit:{output}" if code == 0 else "unknown"


def get_file_changes(base_commit: str) -> tuple[list[dict], dict]:
    """Get list of changed files and summary statistics."""
    # Get file status
    output, code = run_git_command(["git", "diff", "--name-status", f"{base_commit}..HEAD"])
    if code != 0:
        return [], {}

    files = []
    stats = {"added": 0, "modified": 0, "deleted": 0, "renamed": 0}

    for line in output.split("\n"):
        if not line.strip():
            continue

        parts = line.split("\t")
        status = parts[0]
        filepath = parts[1] if len(parts) > 1 else ""

        if status.startswith("A"):
            file_status = "Added"
            stats["added"] += 1
        elif status.startswith("M"):
            file_status = "Modified"
            stats["modified"] += 1
        elif status.startswith("D"):
            file_status = "Deleted"
            stats["deleted"] += 1
        elif status.startswith("R"):
            file_status = "Renamed"
            stats["renamed"] += 1
            if len(parts) > 2:
                filepath = f"{parts[1]} → {parts[2]}"
        else:
            file_status = f"Unknown ({status})"

        files.append({"path": filepath, "status": file_status, "status_code": status})

    return files, stats


def is_binary_file(filepath: str, base_commit: str) -> bool:
    """Check if a file is binary by trying to get its diff."""
    output, code = run_git_command(["git", "diff", "--numstat", f"{base_commit}..HEAD", "--", filepath])

    if code != 0:
        return True

    # Binary files show as "-	-	filename" in numstat
    parts = output.split("\t")
    return len(parts) >= 2 and parts[0] == "-" and parts[1] == "-"


def should_skip_file(filepath: str) -> bool:
    """Check if a file should be skipped (lockfiles, auto-generated files, etc.)."""
    filename = Path(filepath).name.lower()

    # Lock files
    lockfile_patterns = [
        "uv.lock",
        "package-lock.json",
        "yarn.lock",
        "pipfile.lock",
        "poetry.lock",
        "pnpm-lock.yaml",
        "cargo.lock",
        "gemfile.lock",
        "composer.lock",
        "go.sum",
    ]

    # Auto-generated files
    generated_patterns = [
        ".min.js",
        ".min.css",  # Minified files
        ".map",  # Source maps
    ]

    # Check exact filename matches
    if filename in lockfile_patterns:
        return True

    # Check suffix patterns
    for pattern in generated_patterns:
        if filename.endswith(pattern):
            return True

    return False


def get_file_diff(filepath: str, base_commit: str, max_context: int = 3) -> str | None:
    """Get the diff for a specific file."""
    if is_binary_file(filepath, base_commit):
        return None

    output, code = run_git_command(["git", "diff", f"--unified={max_context}", f"{base_commit}..HEAD", "--", filepath])

    if code != 0:
        return None

    return output


def get_file_content(filepath: str) -> str | None:
    """Get the current content of a file (for new files)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def format_diff_for_markdown(diff_output: str, filepath: str, max_unchanged_lines: int = 10) -> str:
    """Format git diff output for markdown with line skipping for large unchanged sections."""
    if not diff_output:
        return ""

    lines = diff_output.split("\n")

    # Skip the git diff header lines (first 4-5 lines typically)
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            content_start = i
            break

    if content_start == 0:
        return ""

    # Get file extension for syntax highlighting
    ext = Path(filepath).suffix.lower()
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "jsx",
        ".tsx": "tsx",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".sh": "bash",
        ".sql": "sql",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".xml": "xml",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".tf": "hcl",
    }

    language = lang_map.get(ext, "")

    # Process diff content
    result_lines = []
    unchanged_count = 0
    in_unchanged_section = False

    for line in lines[content_start:]:
        if line.startswith("@@"):
            # Hunk header
            if unchanged_count > max_unchanged_lines and in_unchanged_section:
                result_lines.append(f"... ({unchanged_count} lines unchanged) ...")
            unchanged_count = 0
            in_unchanged_section = False
            result_lines.append(line)
        elif line.startswith((" ", "\t")) and not line.startswith(("+", "-")):
            # Unchanged line (context)
            unchanged_count += 1
            if unchanged_count <= max_unchanged_lines:
                result_lines.append(line)
            else:
                in_unchanged_section = True
        else:
            # Changed line
            if unchanged_count > max_unchanged_lines and in_unchanged_section:
                result_lines.append(f"... ({unchanged_count} lines unchanged) ...")
            unchanged_count = 0
            in_unchanged_section = False
            result_lines.append(line)

    # Handle trailing unchanged lines
    if unchanged_count > max_unchanged_lines and in_unchanged_section:
        result_lines.append(f"... ({unchanged_count} lines unchanged) ...")

    diff_content = "\n".join(result_lines)

    return f"```{language}\n{diff_content}\n```"


def group_files_by_directory(files: list[dict]) -> dict[str, list[dict]]:
    """Group files by their directory."""
    groups = {}

    for file_info in files:
        filepath = file_info["path"]
        if " → " in filepath:  # Handle renamed files
            filepath = filepath.split(" → ")[1]

        directory = str(Path(filepath).parent)
        if directory == ".":
            directory = "Root"

        if directory not in groups:
            groups[directory] = []
        groups[directory].append(file_info)

    return groups


def generate_markdown_report(base_ref: str, base_commit: str, files: list[dict], stats: dict, output_file: str):
    """Generate the complete markdown report."""
    current_branch = get_current_branch()
    head_commit = get_commit_hash("HEAD")[:8] if get_commit_hash("HEAD") else "unknown"
    base_commit_short = base_commit[:8] if base_commit else "unknown"

    # Calculate total changes
    total_files = len(files)
    binary_files = []

    # Group files by directory
    file_groups = group_files_by_directory(files)

    with open(output_file, "w", encoding="utf-8") as f:
        # Header
        f.write("# Branch Changes Analysis\n\n")
        f.write(f"**Base**: {base_ref} (commit {base_commit_short})\n")
        f.write(f"**Head**: {current_branch} (commit {head_commit})\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Summary
        f.write("## Summary\n\n")
        summary_parts = []
        if stats["added"]:
            summary_parts.append(f"{stats['added']} added")
        if stats["modified"]:
            summary_parts.append(f"{stats['modified']} modified")
        if stats["deleted"]:
            summary_parts.append(f"{stats['deleted']} deleted")
        if stats["renamed"]:
            summary_parts.append(f"{stats['renamed']} renamed")

        f.write(f"- Files changed: {total_files} ({', '.join(summary_parts)})\n")

        # Get line statistics
        output, code = run_git_command(["git", "diff", "--shortstat", f"{base_commit}..HEAD"])
        if code == 0 and output:
            f.write(f"- {output}\n")

        # Changes by directory
        if len(file_groups) > 1:
            f.write("\n## Changes by Directory\n\n")
            for directory, dir_files in sorted(file_groups.items()):
                f.write(f"### `{directory}/` ({len(dir_files)} files)\n")

        # File changes
        f.write("\n## File Changes\n\n")

        for file_info in files:
            filepath = file_info["path"]
            status = file_info["status"]

            # Handle renamed files
            if " → " in filepath:
                old_path, new_path = filepath.split(" → ")
                f.write(f"### `{old_path}` → `{new_path}` ({status})\n\n")
                actual_filepath = new_path
            else:
                f.write(f"### `{filepath}` ({status})\n\n")
                actual_filepath = filepath

            # Skip deleted files (no content to show)
            if status == "Deleted":
                f.write("*File was deleted*\n\n")
                continue

                # Check if binary
            if is_binary_file(actual_filepath, base_commit):
                binary_files.append(actual_filepath)
                f.write("*Binary file (contents not shown)*\n\n")
                continue

            # Check if file should be skipped (lockfiles, etc.)
            if should_skip_file(actual_filepath):
                f.write("*Auto-generated file (skipped for brevity)*\n\n")
                continue

            # For new files, show content directly without diff markers
            if status == "Added":
                file_content = get_file_content(actual_filepath)
                if file_content:
                    # Get file extension for syntax highlighting
                    ext = Path(actual_filepath).suffix.lower()
                    lang_map = {
                        ".py": "python",
                        ".js": "javascript",
                        ".ts": "typescript",
                        ".jsx": "jsx",
                        ".tsx": "tsx",
                        ".java": "java",
                        ".cpp": "cpp",
                        ".c": "c",
                        ".h": "c",
                        ".rs": "rust",
                        ".go": "go",
                        ".rb": "ruby",
                        ".php": "php",
                        ".sh": "bash",
                        ".sql": "sql",
                        ".md": "markdown",
                        ".yaml": "yaml",
                        ".yml": "yaml",
                        ".json": "json",
                        ".xml": "xml",
                        ".html": "html",
                        ".css": "css",
                        ".scss": "scss",
                        ".tf": "hcl",
                    }
                    language = lang_map.get(ext, "")
                    f.write(f"```{language}\n{file_content}\n```\n\n")
                else:
                    f.write("*Could not read file content*\n\n")
            else:
                # Get and format diff for modified files
                diff_output = get_file_diff(actual_filepath, base_commit)
                if diff_output:
                    formatted_diff = format_diff_for_markdown(diff_output, actual_filepath)
                    if formatted_diff:
                        f.write(formatted_diff)
                        f.write("\n\n")
                    else:
                        f.write("*No diff available*\n\n")
                else:
                    f.write("*Could not generate diff*\n\n")

        # Binary files summary
        if binary_files:
            f.write("## Binary Files (Skipped)\n\n")
            for binary_file in binary_files:
                f.write(f"- `{binary_file}`\n")

    print(f"Report generated: {output_file}")
    print(f"Files analyzed: {total_files}")
    if binary_files:
        print(f"Binary files skipped: {len(binary_files)}")


def main():
    parser = argparse.ArgumentParser(description="Generate markdown report of git branch changes")
    parser.add_argument("--base", help="Base branch name (e.g., main, master)")
    parser.add_argument("--base-commit", help="Base commit hash to compare against")
    parser.add_argument("--output", default="changes.md", help="Output markdown file (default: changes.md)")

    args = parser.parse_args()

    # Validate that we're in a git repository
    _, code = run_git_command(["git", "rev-parse", "--git-dir"])
    if code != 0:
        print("Error: Not in a git repository")
        sys.exit(1)

    # Determine base commit
    base_commit = None
    base_ref = None

    if args.base_commit:
        base_commit = get_commit_hash(args.base_commit)
        if not base_commit:
            print(f"Error: Invalid commit hash '{args.base_commit}'")
            sys.exit(1)
        base_ref = args.base_commit
    elif args.base:
        base_commit = get_merge_base(args.base)
        if not base_commit:
            print(f"Error: Could not find merge base with branch '{args.base}'")
            sys.exit(1)
        base_ref = args.base
    else:
        # Try to auto-detect base branch
        for branch in ["main", "master", "develop"]:
            base_commit = get_merge_base(branch)
            if base_commit:
                base_ref = branch
                break

        if not base_commit:
            print("Error: Could not auto-detect base branch. Please specify --base or --base-commit")
            sys.exit(1)

        print(f"Auto-detected base branch: {base_ref}")

    # Get file changes
    files, stats = get_file_changes(base_commit)

    if not files:
        print("No changes found between base and HEAD")
        sys.exit(0)

    # Generate report
    generate_markdown_report(base_ref, base_commit, files, stats, args.output)


if __name__ == "__main__":
    main()

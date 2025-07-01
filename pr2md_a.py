#!/usr/bin/env python3
"""
Generate PR Summary Script

Automatically generates a comprehensive markdown summary of changes between git branches or commits.
Similar to manually created PR summaries but generated algorithmically.

OVERVIEW:
---------
This script analyzes git diffs and creates structured markdown documentation showing:
- Summary statistics (files changed, lines added/removed)
- Full content of new files with syntax highlighting
- Diffs for modified files showing exactly what changed
- Information about deleted and renamed files
- Automatic exclusion of binary files and common generated files

USAGE:
------
Basic usage:
    python generate_pr_summary.py
    python generate_pr_summary.py --base main --output pr_changes.md

Compare specific references:
    python generate_pr_summary.py --base develop --current feature/new-feature
    python generate_pr_summary.py --base abc123 --current def456
    python generate_pr_summary.py --base v1.0.0 --current HEAD

File filtering:
    python generate_pr_summary.py --include-extensions .py,.js,.ts
    python generate_pr_summary.py --exclude-patterns "*.lock,dist/,__pycache__"
    python generate_pr_summary.py --max-file-size 50000

ARGUMENTS:
----------
Reference Options:
  --base, --base-branch, --base-commit
                        Base branch or commit to compare against (default: main)
                        Can be any valid git reference: branch name, commit hash, tag

  --current, --current-branch, --current-commit
                        Current branch or commit with changes (default: HEAD)
                        Can be any valid git reference: branch name, commit hash, tag

Output Options:
  --output, -o          Output file name (default: pr_changes.md)

Filtering Options:
  --max-file-size       Maximum file size to include in full (bytes, default: 100000)
                        Files larger than this will show diffs instead of full content

  --context-lines       Number of context lines in diffs (default: 3)

  --include-extensions  Comma-separated list of file extensions to include
                        Example: .py,.js,.ts,.md
                        If specified, only files with these extensions are processed

  --exclude-patterns    Comma-separated list of patterns to exclude
                        Example: "*.lock,dist/,__pycache__,node_modules"
                        Supports glob patterns and substring matching

EXAMPLES:
---------
1. Compare current branch to main:
   python generate_pr_summary.py

2. Compare specific feature branch to develop:
   python generate_pr_summary.py --base develop --current feature/user-auth

3. Compare two specific commits:
   python generate_pr_summary.py --base a1b2c3d --current e4f5g6h

4. Compare with custom output file:
   python generate_pr_summary.py --base main --output my_feature_summary.md

5. Only include Python and JavaScript files:
   python generate_pr_summary.py --include-extensions .py,.js,.ts,.tsx

6. Exclude lock files and build directories:
   python generate_pr_summary.py --exclude-patterns "*.lock,dist/,build/,__pycache__"

7. Compare release tags:
   python generate_pr_summary.py --base v1.0.0 --current v1.1.0

8. Increase context lines for larger diffs:
   python generate_pr_summary.py --context-lines 5

OUTPUT FORMAT:
--------------
The generated markdown includes:

1. Summary Section:
   - List of new, modified, deleted, and renamed files
   - Statistics: files changed, lines added/removed, commit range

2. New Files Section:
   - Full content of each new file with syntax highlighting
   - Automatically detects file type for proper highlighting

3. Modified Files Section:
   - Git diffs showing exactly what changed in each file
   - Context lines around changes for better understanding

4. Other Changes Section:
   - Information about deleted files
   - Details about renamed files and whether they have content changes

5. Technical Summary Section:
   - Placeholder for manual technical overview

AUTOMATIC EXCLUSIONS:
--------------------
The following file types are automatically excluded as binary files:
- Lock files: *.lock, uv.lock, package-lock.json, yarn.lock
- Images: *.jpg, *.png, *.gif, *.ico, *.svg, *.bmp
- Fonts: *.woff, *.woff2, *.ttf, *.eot, *.otf
- Archives: *.zip, *.tar, *.gz, *.rar, *.7z
- Executables: *.exe, *.dll, *.so, *.dylib, *.a, *.lib
- Media: *.mp3, *.mp4, *.avi, *.mov, *.wav
- Common build artifacts and cache directories

REQUIREMENTS:
-------------
- Must be run from within a git repository
- Git must be available in PATH
- Python 3.7+ (uses pathlib, subprocess, typing)
- The specified git references must exist and be accessible

ERROR HANDLING:
---------------
The script gracefully handles:
- Invalid git references with clear error messages
- Binary files by excluding them from content display
- Large files by falling back to diff display
- Missing files or git errors by logging and continuing
- Redis connectivity issues in deduplication systems (if applicable)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class FileChange(NamedTuple):
    """Represents a single file change in the diff."""

    status: str  # A, M, D, R, C, etc.
    path: str
    old_path: str | None = None  # For renames


class GitError(Exception):
    """Custom exception for git-related errors."""

    pass


class PRSummaryGenerator:
    """Generates comprehensive PR summaries from git diffs."""

    def __init__(
        self,
        base_ref: str,
        current_ref: str,
        output_file: str,
        max_file_size: int = 100000,
        context_lines: int = 3,
        include_extensions: set[str] | None = None,
        exclude_patterns: set[str] | None = None,
    ):
        self.base_ref = base_ref
        self.current_ref = current_ref
        self.output_file = output_file
        self.max_file_size = max_file_size
        self.context_lines = context_lines
        self.include_extensions = include_extensions or set()
        self.exclude_patterns = exclude_patterns or {
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".git",
            "node_modules",
            "*.min.js",
            "*.bundle.js",
            ".env",
            ".env.*",
            "uv.lock",
            "*.lock",
            "*.jpg",
            "*.jpeg",
            "*.png",
            "*.gif",
            "*.ico",
            "*.svg",
            "*.woff",
            "*.woff2",
            "*.ttf",
            "*.eot",
            "*.pdf",
            "*.zip",
            "*.tar.gz",
            "*.exe",
            "*.dll",
            "*.so",
        }

        # Validate git repository
        self._ensure_git_repo()

    def _run_git_command(self, cmd: list[str], allow_empty: bool = False) -> str:
        """Run a git command and return the output."""
        try:
            result = subprocess.run(["git"] + cmd, capture_output=True, text=True, check=True, cwd=os.getcwd())
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if allow_empty and e.returncode == 1 and not e.stderr:
                return ""
            raise GitError(f"Git command failed: {' '.join(cmd)}\nError: {e.stderr}")

    def _ensure_git_repo(self):
        """Ensure we're in a git repository and refs exist."""
        try:
            self._run_git_command(["rev-parse", "--git-dir"])
        except GitError:
            raise GitError("Not in a git repository")

        # Validate refs exist
        try:
            self._run_git_command(["rev-parse", "--verify", self.base_ref])
            self._run_git_command(["rev-parse", "--verify", self.current_ref])
        except GitError as e:
            raise GitError(f"Invalid git reference: {e}")

    def _should_include_file(self, file_path: str) -> bool:
        """Determine if a file should be included in the summary."""
        path = Path(file_path)

        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if pattern.startswith("*"):
                if file_path.endswith(pattern[1:]):
                    return False
            elif pattern in file_path:
                return False

        # Check include extensions (if specified)
        if self.include_extensions:
            return path.suffix in self.include_extensions

        return True

    def _is_binary_file(self, file_path: str, ref: str) -> bool:
        """Check if a file is binary at a specific git ref."""
        try:
            # Check file extension first for common binary types
            path = Path(file_path)
            binary_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".ico",
                ".svg",
                ".bmp",
                ".woff",
                ".woff2",
                ".ttf",
                ".eot",
                ".otf",
                ".pdf",
                ".zip",
                ".tar",
                ".gz",
                ".rar",
                ".7z",
                ".exe",
                ".dll",
                ".so",
                ".dylib",
                ".a",
                ".lib",
                ".mp3",
                ".mp4",
                ".avi",
                ".mov",
                ".wav",
                ".lock",  # treat lock files as binary
            }
            if path.suffix.lower() in binary_extensions:
                return True

            # Use git to check if file is binary
            result = self._run_git_command(["diff", "--numstat", f"{ref}^", ref, "--", file_path], allow_empty=True)
            if result and result.split("\t")[0] == "-":
                return True

            # Additional check: try to read a small portion of the file
            content = self._run_git_command(["show", f"{ref}:{file_path}"], allow_empty=True)
            if content:
                # Check for null bytes (common in binary files)
                return "\0" in content[:1000]

        except GitError:
            pass

        return False

    def _get_file_changes(self) -> list[FileChange]:
        """Get list of changed files between refs."""
        diff_output = self._run_git_command(["diff", "--name-status", f"{self.base_ref}...{self.current_ref}"])

        changes = []
        for line in diff_output.splitlines():
            if not line.strip():
                continue

            parts = line.split("\t")
            status = parts[0]

            if status.startswith("R"):  # Rename
                old_path = parts[1]
                new_path = parts[2]
                changes.append(FileChange("R", new_path, old_path))
            elif status.startswith("C"):  # Copy
                old_path = parts[1]
                new_path = parts[2]
                changes.append(FileChange("C", new_path, old_path))
            else:  # A, M, D
                file_path = parts[1]
                changes.append(FileChange(status, file_path))

        # Filter files
        return [change for change in changes if self._should_include_file(change.path)]

    def _get_file_content(self, file_path: str, ref: str) -> str | None:
        """Get file content at a specific ref."""
        try:
            content = self._run_git_command(["show", f"{ref}:{file_path}"])

            # Check file size
            if len(content.encode("utf-8")) > self.max_file_size:
                return None

            return content
        except GitError:
            return None

    def _get_file_diff(self, file_path: str, old_path: str | None = None) -> str:
        """Get diff for a modified file."""
        try:
            cmd = ["diff", f"--unified={self.context_lines}", f"{self.base_ref}...{self.current_ref}"]
            if old_path:  # Handle renames
                cmd.extend(["--", old_path, file_path])
            else:
                cmd.extend(["--", file_path])

            return self._run_git_command(cmd, allow_empty=True)
        except GitError:
            return ""

    def _get_commit_info(self) -> dict[str, str]:
        """Get information about the commit range."""
        try:
            base_commit = self._run_git_command(["rev-parse", "--short", self.base_ref])
            current_commit = self._run_git_command(["rev-parse", "--short", self.current_ref])

            # Get branch names if possible
            try:
                current_branch = self._run_git_command(["branch", "--show-current"])
            except GitError:
                current_branch = self.current_ref

            return {
                "base_commit": base_commit,
                "current_commit": current_commit,
                "current_branch": current_branch,
                "base_ref": self.base_ref,
                "current_ref": self.current_ref,
            }
        except GitError as e:
            return {"error": str(e)}

    def _get_diff_stats(self) -> dict[str, int]:
        """Get diff statistics."""
        try:
            stats = self._run_git_command(["diff", "--stat", f"{self.base_ref}...{self.current_ref}"])

            # Parse the summary line (e.g., "5 files changed, 123 insertions(+), 45 deletions(-)")
            lines = stats.splitlines()
            if lines:
                summary = lines[-1]
                stats_dict = {"files": 0, "insertions": 0, "deletions": 0}

                if "file" in summary:
                    files_match = re.search(r"(\d+) files? changed", summary)
                    if files_match:
                        stats_dict["files"] = int(files_match.group(1))

                if "insertion" in summary:
                    ins_match = re.search(r"(\d+) insertions?\(\+\)", summary)
                    if ins_match:
                        stats_dict["insertions"] = int(ins_match.group(1))

                if "deletion" in summary:
                    del_match = re.search(r"(\d+) deletions?\(\-\)", summary)
                    if del_match:
                        stats_dict["deletions"] = int(del_match.group(1))

                return stats_dict
        except GitError:
            pass

        return {"files": 0, "insertions": 0, "deletions": 0}

    def _format_file_extension(self, file_path: str) -> str:
        """Get appropriate language identifier for syntax highlighting."""
        ext = Path(file_path).suffix.lower()

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".jsx": "jsx",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".json": "json",
            ".xml": "xml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".sh": "bash",
            ".dockerfile": "dockerfile",
        }

        return ext_map.get(ext, "")

    def _generate_summary_section(
        self, changes: list[FileChange], commit_info: dict[str, str], stats: dict[str, int]
    ) -> str:
        """Generate the summary section of the markdown."""
        added = [c for c in changes if c.status == "A"]
        modified = [c for c in changes if c.status == "M"]
        deleted = [c for c in changes if c.status == "D"]
        renamed = [c for c in changes if c.status == "R"]

        summary = []
        summary.append(f"# PR Changes: {commit_info.get('current_branch', commit_info.get('current_ref'))}")
        summary.append("")
        summary.append("This PR introduces the following changes:")
        summary.append("")
        summary.append("## Summary of Changes")
        summary.append("")

        # File counts
        if added:
            summary.append(f"### New Files Created ({len(added)} files):")
            summary.append("")
            for change in sorted(added, key=lambda x: x.path):
                summary.append(f"- **{change.path}**")
            summary.append("")

        if modified:
            summary.append(f"### Modified Files ({len(modified)} files):")
            summary.append("")
            for change in sorted(modified, key=lambda x: x.path):
                summary.append(f"- **{change.path}**")
            summary.append("")

        if deleted:
            summary.append(f"### Deleted Files ({len(deleted)} files):")
            summary.append("")
            for change in sorted(deleted, key=lambda x: x.path):
                summary.append(f"- **{change.path}**")
            summary.append("")

        if renamed:
            summary.append(f"### Renamed Files ({len(renamed)} files):")
            summary.append("")
            for change in sorted(renamed, key=lambda x: x.path):
                summary.append(f"- **{change.old_path}** → **{change.path}**")
            summary.append("")

        # Statistics
        if stats["files"] > 0:
            summary.append("### Statistics:")
            summary.append("")
            summary.append(f"- **Files Changed**: {stats['files']}")
            if stats["insertions"] > 0:
                summary.append(f"- **Lines Added**: +{stats['insertions']}")
            if stats["deletions"] > 0:
                summary.append(f"- **Lines Removed**: -{stats['deletions']}")
            summary.append(
                f"- **Commit Range**: {commit_info.get('base_commit', self.base_ref)}...{commit_info.get('current_commit', self.current_ref)}"
            )
            summary.append("")

        summary.append("---")
        summary.append("")

        return "\n".join(summary)

    def _generate_new_files_section(self, added_files: list[FileChange]) -> str:
        """Generate section for new files with full content."""
        if not added_files:
            return ""

        sections = []
        sections.append("## New Files")
        sections.append("")

        for change in sorted(added_files, key=lambda x: x.path):
            if self._is_binary_file(change.path, self.current_ref):
                sections.append(f"### {change.path} (Binary File)")
                sections.append("")
                sections.append("*Binary file - content not shown*")
                sections.append("")
                continue

            content = self._get_file_content(change.path, self.current_ref)
            if content is None:
                sections.append(f"### {change.path} (File too large)")
                sections.append("")
                sections.append(f"*File exceeds maximum size limit of {self.max_file_size} bytes*")
                sections.append("")
                continue

            lang = self._format_file_extension(change.path)
            sections.append(f"### {change.path}")
            sections.append("")
            sections.append(f"```{lang}")
            sections.append(content)
            sections.append("```")
            sections.append("")

        return "\n".join(sections)

    def _generate_modified_files_section(self, modified_files: list[FileChange]) -> str:
        """Generate section for modified files with diffs."""
        if not modified_files:
            return ""

        sections = []
        sections.append("## Modified Files")
        sections.append("")

        for change in sorted(modified_files, key=lambda x: x.path):
            if self._is_binary_file(change.path, self.current_ref):
                sections.append(f"### {change.path} (Binary File)")
                sections.append("")
                sections.append("*Binary file modified - diff not shown*")
                sections.append("")
                continue

            diff = self._get_file_diff(change.path)
            if not diff:
                sections.append(f"### {change.path}")
                sections.append("")
                sections.append("*No diff available*")
                sections.append("")
                continue

            sections.append(f"### {change.path}")
            sections.append("")
            sections.append("```diff")
            sections.append(diff)
            sections.append("```")
            sections.append("")

        return "\n".join(sections)

    def _generate_other_changes_section(self, deleted_files: list[FileChange], renamed_files: list[FileChange]) -> str:
        """Generate section for deletions and renames."""
        if not deleted_files and not renamed_files:
            return ""

        sections = []
        sections.append("## Other Changes")
        sections.append("")

        if deleted_files:
            sections.append("### Deleted Files")
            sections.append("")
            for change in sorted(deleted_files, key=lambda x: x.path):
                sections.append(f"- **{change.path}** - File removed")
            sections.append("")

        if renamed_files:
            sections.append("### Renamed Files")
            sections.append("")
            for change in sorted(renamed_files, key=lambda x: x.path):
                diff = self._get_file_diff(change.path, change.old_path)
                if diff and not diff.startswith("similarity index 100%"):
                    sections.append(f"- **{change.old_path}** → **{change.path}** (with modifications)")
                else:
                    sections.append(f"- **{change.old_path}** → **{change.path}** (renamed only)")
            sections.append("")

        return "\n".join(sections)

    def generate_summary(self) -> str:
        """Generate the complete PR summary."""
        print("Analyzing git changes...")

        # Get all changes
        changes = self._get_file_changes()
        if not changes:
            return "# No Changes Found\n\nNo differences detected between the specified references."

        print(f"Found {len(changes)} changed files")

        # Get commit info and stats
        commit_info = self._get_commit_info()
        stats = self._get_diff_stats()

        # Categorize changes
        added_files = [c for c in changes if c.status == "A"]
        modified_files = [c for c in changes if c.status == "M"]
        deleted_files = [c for c in changes if c.status == "D"]
        renamed_files = [c for c in changes if c.status == "R"]

        print(
            f"Added: {len(added_files)}, Modified: {len(modified_files)}, Deleted: {len(deleted_files)}, Renamed: {len(renamed_files)}"
        )

        # Generate sections
        summary_section = self._generate_summary_section(changes, commit_info, stats)
        new_files_section = self._generate_new_files_section(added_files)
        modified_files_section = self._generate_modified_files_section(modified_files)
        other_changes_section = self._generate_other_changes_section(deleted_files, renamed_files)

        # Technical summary
        technical_summary = [
            "## Technical Summary",
            "",
            "*This section should be filled with a high-level technical overview of the changes.*",
            "",
            "Key technical aspects:",
            "- *[Add key technical points]*",
            "- *[Add architectural changes]*",
            "- *[Add performance implications]*",
            "",
        ]

        # Combine all sections
        result = []
        result.append(summary_section)
        if new_files_section:
            result.append(new_files_section)
        if modified_files_section:
            result.append(modified_files_section)
        if other_changes_section:
            result.append(other_changes_section)
        result.append("\n".join(technical_summary))

        return "\n".join(result)

    def save_summary(self, content: str):
        """Save the summary to the output file."""
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"PR summary saved to: {self.output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive PR summaries from git diffs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --base main --output pr_changes.md
  %(prog)s --base abc123 --current def456
  %(prog)s --base develop --include-extensions .py,.js,.ts
  %(prog)s --current feature/new-feature --exclude-patterns "*.lock,dist/"
        """,
    )

    # Reference options
    parser.add_argument(
        "--base",
        "--base-branch",
        "--base-commit",
        dest="base_ref",
        default="main",
        help="Base branch or commit to compare against (default: main)",
    )

    parser.add_argument(
        "--current",
        "--current-branch",
        "--current-commit",
        dest="current_ref",
        help="Current branch or commit with changes (default: HEAD)",
    )

    # Output options
    parser.add_argument("--output", "-o", default="pr_changes.md", help="Output file name (default: pr_changes.md)")

    # Filtering options
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=100000,
        help="Maximum file size to include in full (bytes, default: 100000)",
    )
    parser.add_argument("--context-lines", type=int, default=3, help="Number of context lines in diffs (default: 3)")
    parser.add_argument(
        "--include-extensions", help="Comma-separated list of file extensions to include (e.g., .py,.js,.ts)"
    )
    parser.add_argument(
        "--exclude-patterns", help='Comma-separated list of patterns to exclude (e.g., "*.lock,dist/,__pycache__")'
    )

    args = parser.parse_args()

    # Determine references
    base_ref = args.base_ref
    current_ref = args.current_ref or "HEAD"

    # Parse filtering options
    include_extensions = set()
    if args.include_extensions:
        include_extensions = set(ext.strip() for ext in args.include_extensions.split(","))

    exclude_patterns = {
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".git",
        "node_modules",
        "*.min.js",
        "*.bundle.js",
        ".env",
        ".env.*",
        "uv.lock",
        "*.lock",
    }
    if args.exclude_patterns:
        exclude_patterns.update(pattern.strip() for pattern in args.exclude_patterns.split(","))

    try:
        # Create generator
        generator = PRSummaryGenerator(
            base_ref=base_ref,
            current_ref=current_ref,
            output_file=args.output,
            max_file_size=args.max_file_size,
            context_lines=args.context_lines,
            include_extensions=include_extensions if include_extensions else None,
            exclude_patterns=exclude_patterns,
        )

        # Generate and save summary
        summary = generator.generate_summary()
        generator.save_summary(summary)

        print("✓ PR summary generated successfully!")

    except GitError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

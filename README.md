# PR to Markdown

Powerful command-line tools for generating comprehensive markdown reports from git changes. Perfect for PR reviews, documentation, and change analysis.

## 🚀 Overview

Both tools do the same core task: **generate markdown reports from git changes**. The difference is in the level of customization and options available.

- **`pr2md_a.py`** - Advanced version with extensive customization options
- **`pr2md_b.py`** - Streamlined version with sensible defaults and fewer options

## 📊 Feature Comparison

| Feature                          | pr2md_a.py (Advanced)                    | pr2md_b.py (Simple)                      |
| -------------------------------- | ---------------------------------------- | ---------------------------------------- |
| **Core Functionality**           | ✅ Generate markdown from git changes    | ✅ Generate markdown from git changes    |
| **Compare any git refs**         | ✅ Branches, commits, tags               | ✅ Branches, commits, tags               |
| **New file content**             | ✅ Full content with syntax highlighting | ✅ Full content with syntax highlighting |
| **Modified file diffs**          | ✅ Unified diffs with context            | ✅ Unified diffs with context            |
| **Binary file detection**        | ✅ Automatic exclusion                   | ✅ Automatic exclusion                   |
| **Auto-generated file handling** | ✅ Smart exclusion patterns              | ✅ Smart exclusion patterns              |
|                                  |                                          |                                          |
| **Advanced Options**             |                                          |                                          |
| **Custom file filtering**        | ✅ Include/exclude by extension/pattern  | ❌ Built-in patterns only                |
| **Configurable diff context**    | ✅ Adjustable context lines              | ❌ Fixed at 3 lines                      |
| **File size limits**             | ✅ Configurable max file size            | ❌ No size limits                        |
| **Directory grouping**           | ❌ Files listed individually             | ✅ Organized by directory                |
| **Merge base auto-detection**    | ❌ Must specify base ref                 | ✅ Auto-detects common branches          |
| **Extensive error handling**     | ✅ Detailed validation and errors        | ✅ Basic error handling                  |

## 📦 Installation

### Prerequisites

- Python 3.11+ (for pr2md_b.py) or Python 3.7+ (for pr2md_a.py)
- Git installed and available in PATH
- Must be run from within a git repository

### Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd pr-to-md

# No external dependencies required - uses only Python standard library
# Optional: create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

## 🎯 Quick Start

### Using the Advanced Version (`pr2md_a.py`)

```bash
# Basic usage - compare current branch to main
python pr2md_a.py

# Compare specific branches
python pr2md_a.py --base develop --current feature/new-feature

# Compare commits with custom output
python pr2md_a.py --base abc123 --current def456 --output my_changes.md

# Filter by file types
python pr2md_a.py --include-extensions .py,.js,.ts

# Exclude patterns
python pr2md_a.py --exclude-patterns "*.lock,dist/,__pycache__"
```

### Using the Simple Version (`pr2md_b.py`)

```bash
# Auto-detect base and generate analysis
python pr2md_b.py

# Compare with specific branch
python pr2md_b.py --base main

# Compare with specific commit
python pr2md_b.py --base-commit abc123

# Custom output file
python pr2md_b.py --base main --output my_analysis.md
```

## 📖 Detailed Usage

### pr2md_a.py Options

| Option                 | Description                            | Example                             |
| ---------------------- | -------------------------------------- | ----------------------------------- |
| `--base`               | Base branch/commit to compare against  | `--base main`                       |
| `--current`            | Current branch/commit with changes     | `--current feature/auth`            |
| `--output`             | Output markdown file name              | `--output pr_summary.md`            |
| `--max-file-size`      | Max file size for full content (bytes) | `--max-file-size 50000`             |
| `--context-lines`      | Number of context lines in diffs       | `--context-lines 5`                 |
| `--include-extensions` | Comma-separated file extensions        | `--include-extensions .py,.js`      |
| `--exclude-patterns`   | Patterns to exclude                    | `--exclude-patterns "*.lock,dist/"` |

### pr2md_b.py Options

| Option          | Description                    | Example                |
| --------------- | ------------------------------ | ---------------------- |
| `--base`        | Base branch to compare against | `--base develop`       |
| `--base-commit` | Specific base commit           | `--base-commit abc123` |
| `--output`      | Output markdown file name      | `--output changes.md`  |

## 📋 Output Examples

Both tools generate well-structured markdown with:

- **Summary Statistics**: Files changed, lines added/removed, commit information
- **New Files**: Complete file content with syntax highlighting
- **Modified Files**: Clean unified diffs showing exactly what changed
- **File Organization**: Grouped by type or directory for easy navigation
- **Smart Handling**: Binary files, lockfiles, and large files handled appropriately

### Sample Output Structure

```markdown
# PR Summary / Branch Changes Analysis

## Summary

- Files changed: 12 (8 added, 3 modified, 1 deleted)
- Base: main (commit a1b2c3d4)
- Head: feature/auth (commit e5f6g7h8)

## New Files

### `src/auth/login.py`

[Full file content with Python syntax highlighting]

## Modified Files

### `src/config.py`

[Clean diff showing only the changes]

## Other Changes

### Deleted Files

- `old_module.py`
```

## 🔧 Development

### Project Structure

```
pr-to-md/
├── pr2md_a.py          # Advanced version with more options
├── pr2md_b.py          # Simple version with sensible defaults
├── README.md           # This file
├── LICENSE            # MIT License
└── .gitignore         # Python gitignore
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Documentation**: Check this README and the built-in help (`python pr2md_a.py --help`)
- **Examples**: See the usage examples above

## 🏷️ Version

Current version: 1.0.0

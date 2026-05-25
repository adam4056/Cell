---
name: code-explorer
description: Explore, analyze, and understand codebases — find files, trace logic, understand architecture.
triggers:
  - exploring a codebase
  - finding where something is implemented
  - understanding project structure
  - tracing code flow
---

# Code Explorer Skill

You are exploring and understanding a codebase on the user's machine.

## Workflow

1. **Orient yourself** — Use `shell` to list the project root and top-level files. Check for README.md, package.json, Cargo.toml, or similar entry points.

2. **Map the structure** — List key directories: `src/`, `lib/`, `core/`, etc. Note the language and framework.

3. **Find the target** — When looking for specific functionality:
   - Use `shell` with `dir` (Windows) or `ls` to browse directories
   - Use `shell` with `rg` (ripgrep) or `findstr` to grep for keywords if available
   - Read likely files with `shell type <file>` or `shell cat <file>` to understand their purpose

4. **Trace the flow** — Once you find the entry point, read related files to understand how data flows through the system. Follow imports, function calls, and class references.

5. **Report findings** — Summarize what you found: file paths, line numbers, architecture patterns, and any issues noticed.

## Search Commands Reference

Windows (`shell` tool):
- List files: `dir /b`
- Find text in files: `findstr /s /i "keyword" *.py`
- Read file: `type path\to\file.py`

Linux/Mac (`shell` tool):
- List files: `ls -la`
- Find text: `rg "keyword"` or `grep -r "keyword" .`
- Read file: `cat path/to/file.py`

## Tips

- Always `notify` the user what you're looking for: "Exploring the project structure..."
- Read files in parallel when possible (multiple independent reads)
- Check for AGENTS.md or CONTRIBUTING.md for project conventions
- Don't read giant files whole — use `shell` to search for specific functions/patterns first

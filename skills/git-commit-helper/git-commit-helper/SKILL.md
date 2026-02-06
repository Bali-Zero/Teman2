---
name: git-commit-helper
description: Assists with git commits by fixing common pre-commit issues (e.g., print() statements), staging changes, generating commit messages, and providing deployment instructions. Use when preparing to commit and push changes, especially after local development or fixes.
---

# Git Commit Helper

## Overview

This skill streamlines the `git commit` process by automating common pre-commit tasks, handling commit message generation, and providing clear instructions for subsequent `git push` and deployment monitoring. It aims to improve developer workflow efficiency and adherence to project standards.

## Workflow

The `git-commit-helper` executes the following steps:

1.  **Identify and Fix Pre-commit Issues:**
    - Scans staged Python files for `print()` statements and automatically replaces them with `logging` calls (`logger.info`, `logger.error`, etc.).
    - Ensures `import logging` and `logger = logging.getLogger(__name__)` are present in affected files.
    - _Note:_ This step specifically addresses the "no `print()` statements" pre-commit hook often found in Python projects.

2.  **Stage All Relevant Changes:**
    - Stages all modified tracked files (`git add -u`).
    - Selectively stages untracked files that appear to be legitimate project components (e.g., Python scripts, documentation, new source files), while ignoring temporary or tool-specific files.

3.  **Generate Commit Message:**
    - Creates a comprehensive commit message following Conventional Commits specification, summarizing the changes made during the session (e.g., fixes for pre-commit issues, new files, consolidated modifications).

4.  **Execute Commit:**
    - Performs the `git commit` operation. If pre-commit hooks are still failing despite automated fixes (due to false positives or misconfiguration), it may suggest bypassing them (`--no-verify`) as a last resort, with appropriate warnings.

5.  **Provide Deployment Instructions & Monitor (Enhanced Autonomy):**
    - After a successful commit, it will provide the necessary `git push` command.
    - **Upon confirmation of `git push` (or explicit user request), the skill will attempt to automatically monitor deployments.**
    - It will check for installed Vercel and Fly.io CLIs.
    - If found, it will stream real-time deployment logs from Vercel (for frontend `apps/mouth`) and Fly.io (for backend `apps/backend-rag`) directly into the chat, providing autonomous monitoring.
    - Offers clear guidance on how to manually monitor deployments if automated monitoring is not possible.

## Resources

This skill will primarily utilize `scripts/` for automated fixes and potentially `references/` for commit message templates or deployment checklists.

### scripts/

Executable Python scripts will be used to automate the detection and replacement of `print()` statements with `logger` calls, similar to the process just completed. New scripts will also be added for automated deployment monitoring (e.g., `monitor_vercel.py`, `monitor_flyio.py`).

### references/

Might include templates for generating standardized commit messages or detailed deployment checklists specific to this project's environments (Vercel, Fly.io).

---

# GitHub / VS Code starter workflow

## Initialize locally

From the repository root:

```bash
git init
git add .
git status
make verify
git commit -m "Initial AIM 5.9 Wine compatibility scaffold"
```

## Create GitHub repository with GitHub CLI

Example:

```bash
gh repo create rrlzAIM --public --source=. --remote=origin --push
```

Change visibility/name as desired.

## Suggested first Codex instruction

```text
Read AGENTS.md and all docs before making changes.

Audit the repository against the documented versioned Wine AIM sound fixes.

Do not add any AOL/AIM binaries.
Do not change the supported AIM or Wine versions without the required validation.
Run make verify.
Show me the diff before committing.
```

## VS Code

The repository includes `.vscode/tasks.json` with tasks for:

- Verify repository
- Verify published DLL
- Build patched mciwave
- Build release artifacts

Use **Terminal -> Run Task**.

# Git Guide — Safe Workflow for PBTES Simulations

You do NOT need to be a git expert. Just follow these 3 patterns and you
will never lose working code again.

---

## The Golden Rule

> **`main` branch = always working. Experiments = always on branches.**

You can try anything on a branch. If it breaks, delete the branch.
`main` stays untouched. This is the entire point of git.

---

## Pattern 1: Making a safe change (normal work)

```bash
# 1. Create a new branch from main
git checkout main
git checkout -b fix/improve-mode-4

# 2. Edit files, test, iterate...
python -m pytest tests/ -x

# 3. When done, stage and commit
git add -A
git commit -m "fix: improve mode 4 convergence"

# 4. Go back to main and merge
git checkout main
git merge fix/improve-mode-4

# 5. Push to GitHub (backup!)
git push

# 6. Clean up the branch (optional)
git branch -d fix/improve-mode-4
```

**That's it.** No more fear of breaking things.

---

## Pattern 2: Risky experiment (you think it might break things)

```bash
# Create an experiment branch
git checkout -b experiment/try-something-crazy

# Edit, test, try anything...
# ——— if it DOESN'T work and you want to ABANDON it ———

# Go back to main
git checkout main

# Delete the broken branch (NOTHING in main is affected)
git branch -D experiment/try-something-crazy

# ——— if it DOES work and you want to KEEP it ———

git checkout main
git merge experiment/try-something-crazy
git push
```

**The experiment branch is a sandbox.** Delete or keep it — main stays safe.

---

## Pattern 3: Agent is working on a branch (you want to check)

```bash
# See all branches
git branch

# Switch to the agent's branch to inspect
git checkout refactor/extract-solver

# Look around, maybe run tests
python -m pytest tests/ -x

# Go back to your main branch
git checkout main
```

---

## Common commands (print this and keep it)

| When you want to... | Command |
|---------------------|---------|
| See what changed since last commit | `git status` |
| See exactly what changed in files | `git diff` |
| See recent history | `git log --oneline -10` |
| Undo an uncommitted change to a file | `git checkout -- <filename>` |
| Go back to last commit (discard all uncommitted) | `git reset --hard HEAD` |
| See what branch you're on | `git branch` |
| Create and switch to new branch | `git checkout -b <name>` |
| Switch to an existing branch | `git checkout <name>` |
| Save your work (commit) | `git add -A` then `git commit -m "message"` |
| Send work to GitHub | `git push` |
| Get latest from GitHub | `git pull` |

---

## Branch naming

| Prefix | For |
|--------|-----|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `refactor/` | Reorganizing code, no behavior change |
| `experiment/` | Risky ideas, may be deleted |
| `test/` | Adding or fixing tests |

Good examples: `feature/add-monthly-report`, `fix/mode-3-convergence`, `refactor/extract-packed-bed`

---

## What to NEVER do

- ❌ `git push --force` — can destroy work on GitHub
- ❌ `git commit --amend` on something you already pushed
- ❌ Committing directly to `main` (agents are forbidden from this)

---

## If something goes wrong

**Don't panic.** Git never truly deletes anything for 30+ days.

```bash
# If you committed to the wrong branch by accident:
git log --oneline -5              # find the commit hash (e.g., abc1234)
git checkout correct-branch
git cherry-pick abc1234           # bring that commit to the right branch
git checkout wrong-branch
git reset --hard HEAD~1           # remove it from the wrong branch

# If you want to see something you deleted:
git reflog                        # shows everything you've done
```

---

## GitHub

### First-time setup (if not done yet)
```bash
gh auth login
# Follow prompts — choose HTTPS, Login with a web browser
```

### Create the repo on GitHub
```bash
gh repo create pbtes-sim --public --push --source .
```

### Everyday backup
```bash
git push          # sends your work to GitHub
git pull          # gets latest from GitHub
```

---

*Last updated: 2026-05-19 — git + GitHub initialized for this project.*

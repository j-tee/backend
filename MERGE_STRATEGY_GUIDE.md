# Git Merge Strategy Guide

## Branch Workflow

This project uses a **three-tier branching strategy**:

```
Feature Branches → development → main
```

### Branch Purposes

1. **Feature Branches** (e.g., `AI-platform-mngt`, `inventory-feature`)
   - Active development work
   - Bug fixes
   - New features

2. **`development`** (Integration Branch)
   - Integration point for all features
   - Testing ground before production
   - Always merge feature branches here FIRST

3. **`main`** (Production Branch)
   - Production-ready code only
   - Only receives merges from `development`
   - Never merge feature branches directly here

---

## ✅ CORRECT Merge Flow

### Step 1: Merge Feature → Development

```bash
# 1. Ensure your feature branch is up to date
git checkout AI-platform-mngt
git pull origin AI-platform-mngt

# 2. Switch to development and update it
git checkout development
git pull origin development

# 3. Merge your feature branch into development
git merge AI-platform-mngt

# 4. Resolve any conflicts if needed
# 5. Test thoroughly

# 6. Push to remote
git push origin development
```

### Step 2: Merge Development → Main

```bash
# 1. Ensure development is up to date
git checkout development
git pull origin development

# 2. Switch to main and update it
git checkout main
git pull origin main

# 3. Merge development into main
git merge development

# 4. Push to remote
git push origin main
```

---

## ❌ AVOID: Direct Feature → Main Merges

**DO NOT** do this:
```bash
git checkout main
git merge AI-platform-mngt  # ❌ WRONG!
```

### Why This Causes Problems

1. **Bypasses Integration Testing**: `development` serves as the integration testing ground
2. **Creates Branch Divergence**: `development` becomes out of sync with `main`
3. **Causes Merge Conflicts**: Future merges become complicated
4. **Loses Track of Changes**: Harder to track what went into production and when

---

## 🚨 If You Accidentally Merged Feature → Main

### Recovery Steps

1. **Don't Panic** - The changes are not lost

2. **Sync Development Branch**:
```bash
# Get development up to date with main
git checkout development
git pull origin development
git merge main
git push origin development
```

3. **Update Feature Branch**:
```bash
# Sync your feature branch with development
git checkout AI-platform-mngt
git merge development
git push origin AI-platform-mngt
```

---

## Quick Reference Checklist

Before merging, always ask:

- [ ] Is my feature branch tested and working?
- [ ] Have I pulled the latest changes from origin?
- [ ] Am I merging to `development` first (not `main`)?
- [ ] Have I resolved all conflicts?
- [ ] Have I tested after the merge?

---

## Current Branch Status

You can check your branch relationships anytime:

```bash
# See branch history graph
git log --oneline --graph --decorate --all -15

# Check which branch you're on
git branch

# See remote branches
git branch -r

# Check if branches are in sync
git fetch --all
git status
```

---

## Pull Request Strategy (GitHub)

When using GitHub Pull Requests:

1. **Feature → Development**: Create PR from feature branch to `development`
2. **Development → Main**: Create PR from `development` to `main`

**Never create**: Feature → Main (unless in emergency and coordinated with team)

---

## Notes

- **Last Updated**: November 9, 2025
- **Project**: POS Backend
- **Repository**: j-tee/backend

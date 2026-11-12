# Oude Mechanismen ↔ Antigravity: Pairing Quick Start Guide

**Version:** 1.0  
**Last Updated:** 2026-11-12  

---

## 🎯 What This Guide Covers

This guide helps you **pair development on `oude-mechanismen` with reviews using Gemini Antigravity** in under 5 minutes.

---

## 🚀 Quick Start (TL;DR)

### For Developers: Request a Review

```bash
# 1. Make your changes
git add .
git commit -m "feat: add new skill [REVIEW-REQUESTED]"
git push
```

That's it! The automated workflow will:
- Detect your review request
- Create a review stub document
- Notify Antigravity to start the Goldfish Review
- Post updates to your PR

### For Reviewers: Perform a Goldfish Review

```bash
# 1. Navigate to the review document
gemini worktree add oude-mechanismen ~/Repos/oude-mechanismen

# 2. Open the review document
# (Created automatically at docs/reviews/pr_<number>_review.md)

# 3. Execute adversarial probes
# (See docs/REVIEW_PAIRING.md for probe templates)

# 4. Document findings and set verdict
```

---

## 📋 Step-by-Step Setup

### Prerequisites

- ✅ GitHub account with access to `terra-campaigns/oude-mechanismen`
- ✅ **Gemini Antigravity** installed and configured
- ✅ Local clone of `oude-mechanismen` at `~/Repos/oude-mechanismen`

### Step 1: Configure Antigravity Skills Discovery

```bash
# Create Gemini config directory
mkdir -p ~/.gemini/config

# Configure skills.json to discover oude-mechanismen skills
cat > ~/.gemini/config/skills.json << 'EOF'
{
  "entries": [
    {
      "path": "~/Repos/oude-mechanismen/skills"
    },
    {
      "path": "~/Repos/artifice/skills"
    }
  ]
}
EOF

# Restart Antigravity to load the new configuration
```

**Verify:**
```bash
# Check that Antigravity can discover the skills
ls -la ~/Repos/oude-mechanismen/skills/
# Should see: add-chapter, add-character, illustrate-entry, lint-wiki, lookup-context, prep-session, review-style, scribe-session, weave-threads
```

### Step 2: Create a Worktree for Active Development

```bash
# Add a worktree for the main branch
gemini worktree add oude-mechanismen ~/Repos/oude-mechanismen

# List worktrees to verify
gemini worktree list
```

### Step 3: Test the Pairing

```bash
# Make a test change
echo "# Test" > /tmp/test_review.md

# Commit with review request tag
git add /tmp/test_review.md
git commit -m "test: pairing setup [REVIEW-REQUESTED]"
git push

# Check GitHub Actions
# The review-request workflow should trigger automatically
```

---

## 🎨 Common Pairing Scenarios

### Scenario 1: New Skill Development

**Goal:** Add a new procedural skill and get it reviewed

```bash
# 1. Create new skill directory
mkdir -p ~/Repos/oude-mechanismen/skills/new-skill

# 2. Create SKILL.md with proper front matter
cat > ~/Repos/oude-mechanismen/skills/new-skill/SKILL.md << 'EOF'
---
name: new-skill
description: Description of what this skill does
argument-hint: optional argument description
---

# New Skill

Detailed instructions here...
EOF

# 3. Commit with review request
git add skills/new-skill/
git commit -m "feat: add new-skill [REVIEW-REQUESTED]"
git push

# 4. Antigravity will automatically:
#    - Detect the new skill
#    - Run Goldfish Review
#    - Check for: proper front matter, British English, blank lines after headings
#    - Verify no hardcoded lore
```

**Expected Probes:**
- PROBE-01: Front matter schema validation
- PROBE-02: British English compliance
- PROBE-03: Markdown spacing rules
- PROBE-04: No hardcoded setting lore

### Scenario 2: Architecture Decision (ADR)

**Goal:** Propose a new architecture and get it reviewed

```bash
# 1. Create ADR document
NEXT_NUMBER=$(ls docs/adr/ | grep -E '^[0-9]+_' | sort -n | tail -1 | cut -d_ -f1 | awk '{print $1+1}')
cat > docs/adr/${NEXT_NUMBER}_new_architecture.md << 'EOF'
# ADR XXX: New Architecture

- **Status:** Proposed
- **Date:** $(date +%Y-%m-%d)
- **Author:** Your Name (Pair Programming with Antigravity)

---

## 1. Context

<Explain the problem>

## 2. Options

<List options considered>

## 3. Decision

<State the decision>

## 4. Consequences

<Positive and negative consequences>
EOF

# 2. Commit with ADR review request
git add docs/adr/${NEXT_NUMBER}_new_architecture.md
git commit -m "docs: ADR XXX draft [ADR-REVIEW][REVIEW-REQUESTED]"
git push
```

**Expected Probes:**
- PROBE-01: Option analysis completeness
- PROBE-02: Consequence documentation
- PROBE-03: Backward compatibility
- PROBE-04: Implementation feasibility

### Scenario 3: Bug Fix with Probe Reference

**Goal:** Fix a bug identified in a previous review

```bash
# 1. Find the probe that needs fixing
grep -r "PROBE-01" docs/reviews/ | head -5

# 2. Implement the fix
# (Edit the relevant files)

# 3. Commit with probe reference
git add .
git commit -m "fix: resolve PROBE-01 path calculation [REVIEW-REQUESTED]"
git push
```

---

## 🔧 Configuration Reference

### Commit Message Tags

| Tag | Purpose | Example |
| :--- | :--- | :--- |
| `[REVIEW-REQUESTED]` | Request standard review | `feat: new feature [REVIEW-REQUESTED]` |
| `[FULL-REVIEW]` | Request comprehensive review | `refactor: core [FULL-REVIEW]` |
| `[ADR-REVIEW]` | Request ADR-specific review | `docs: ADR draft [ADR-REVIEW]` |
| `[PROBE-nn]` | Reference specific probe | `fix: resolve PROBE-01` |
| `[SKIP-REVIEW]` | Skip automated review | `chore: typo fix [SKIP-REVIEW]` |
| `[CO-AUTHORED]` | Co-authored with Antigravity | `feat: new feature [CO-AUTHORED]` |

### Worktree Commands

```bash
# Add a worktree
gemini worktree add <name> <path>

# List worktrees
gemini worktree list

# Switch to a worktree
gemini worktree use <name>

# Remove a worktree
gemini worktree remove <name>
```

### Skills.json Configuration

```json
{
  "entries": [
    {
      "path": "~/Repos/oude-mechanismen/skills"
    },
    {
      "path": "~/Repos/artifice/skills"
    },
    {
      "path": "~/Repos/other-repo/skills"
    }
  ]
}
```

---

## 📊 Monitoring Your Reviews

### Check Review Status

```bash
# List all review documents
ls -la docs/reviews/

# Check a specific review
cat docs/reviews/pr_<number>_review.md

# Check GitHub Actions for workflow status
gh run list --repo terra-campaigns/oude-mechanismen
```

### Review Metrics

| Metric | Command | Target |
| :--- | :--- | :--- |
| Pending reviews | `grep -c "Verdict.*Pending" docs/reviews/*.md` | < 5 |
| Open probes | `grep -c "Status.*Open" docs/reviews/*.md` | 0 |
| Approved reviews | `grep -c "Verdict.*Approved" docs/reviews/*.md` | All requested |
| Average resolution time | Manual tracking | < 24 hours |

---

## ⚠️ Troubleshooting

### Issue: Review workflow not triggering

**Check:**
```bash
# Verify commit message has the tag
git log --oneline -1

# Check workflow file exists
ls -la .github/workflows/review-request.yml

# Check GitHub Actions
gh run list --repo terra-campaigns/oude-mechanismen
```

**Fix:**
- Add `[REVIEW-REQUESTED]` to commit message or PR title
- Push to trigger workflow

### Issue: Antigravity not discovering skills

**Check:**
```bash
# Verify skills.json configuration
cat ~/.gemini/config/skills.json

# Verify path exists
ls -la ~/Repos/oude-mechanismen/skills
```

**Fix:**
- Update `skills.json` with correct path
- Restart Antigravity
- Verify path is accessible

### Issue: Worktree conflicts

**Check:**
```bash
# List existing worktrees
gemini worktree list
```

**Fix:**
```bash
# Remove conflicting worktree
gemini worktree remove <conflicting-name>

# Recreate worktree
gemini worktree add oude-mechanismen ~/Repos/oude-mechanismen
```

### Issue: Probes not being resolved

**Check:**
```bash
# List open probes in a review document
grep "Status.*Open" docs/reviews/pr_<number>_review.md
```

**Fix:**
- Address each probe's issue
- Update the review document with resolution
- Commit with probe reference: `fix: resolve PROBE-nn`

---

## 📚 Learning Resources

### Essential Reading

1. **[REVIEW_PAIRING.md](docs/REVIEW_PAIRING.md)** - Complete pairing workflow specification
2. **[AGENTS.md](AGENTS.md)** - Agentic architecture and implementation manual
3. **[ADR 001](docs/adr/001_dynamic_engine_vs_sync_distribution.md)** - Architecture decision example
4. **[ADR 002](docs/adr/002_python_cli_distribution_uv.md)** - CLI distribution architecture

### Example Reviews

- **[Goldfish Review: The Archival Scriptorium](docs/reviews/001_archival_scriptorium_review.md)** - Complete review with 11 probes

### Templates

- **[Review Document Template](docs/REVIEW_PAIRING.md#appendix-a-probe-templates)**
- **[ADR Template](templates/)** (if available)

---

## 🤝 Co-Authorship

When working with Antigravity, use **co-authorship** to give proper credit:

```bash
# Single commit co-authored
git commit -m "feat: new feature

Co-authored-by: Antigravity <antigravity@gemini.google.com>"

# Multiple co-authors
git commit -m "feat: new feature

Co-authored-by: Antigravity <antigravity@gemini.google.com>
Co-authored-by: Other Developer <other@example.com>"
```

This ensures:
- ✅ Proper attribution in Git history
- ✅ Accurate contribution statistics
- ✅ Recognition of Antigravity's contributions

---

## 🎉 Next Steps

Now that you've set up pairing:

1. **📖 Read the full specification** in [REVIEW_PAIRING.md](docs/REVIEW_PAIRING.md)
2. **🔧 Configure your environment** as shown above
3. **✨ Start pairing** on your next change
4. **📊 Monitor** your review metrics
5. **🤝 Contribute** to improving the pairing process

---

## 📞 Getting Help

- **Documentation:** [REVIEW_PAIRING.md](docs/REVIEW_PAIRING.md)
- **Issues:** Open a GitHub issue in `terra-campaigns/oude-mechanismen`
- **Discussions:** Check the campaign Discord/Slack channels
- **Direct:** Tag `@antigravity` in PR comments

---

*This guide is version 1.0. Feedback and improvements are welcome!*

---
name: code-review
description: >-
  Local CodeRabbit alternative. Use this skill to perform an automated code review on code changes before finalizing a task.
---

# Automated Code Review (CodeRabbit Alternative)

Perform a strict code review on recent changes, evaluating the following criteria:

## Review Checklist
1. **Logic & Correctness**: Does the code do what it's supposed to do? Are there any obvious bugs?
2. **Regressions**: Could this change break existing functionality? (Verify via tests).
3. **Style & Conventions**: Does the code match the existing project style? Are variables named clearly?
4. **Security & Safety**: Are there any hardcoded credentials or unsafe operations?
5. **Performance**: Are there any glaring performance bottlenecks?

## Output format
Produce a brief Review Summary artifact or message outlining:
- **Status**: [Approved | Needs Changes]
- **Issues Found**: (List any bugs, style issues, etc.)
- **Suggestions**: (Optional improvements)

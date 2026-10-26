---
name: ralph-loop
description: >-
  Ralph Loop workflow. Use this skill to enforce iterative implementation, testing, and fixing. It ensures no code is considered done until tests pass.
---

# Ralph Loop Workflow

The Ralph Loop is a strict iterative process to ensure high-quality code delivery.

## The Loop
1. **PLAN**: Outline what needs to be changed.
2. **IMPLEMENT**: Write or modify the code.
3. **TEST**: Run the project's test suite (e.g., `pytest`).
4. **INSPECT FAILURE**: If tests fail, read the error logs carefully. Do not guess.
5. **FIX**: Make the necessary corrections based on the test output.
6. **TEST AGAIN**: Re-run the tests.
7. **REVIEW**: Perform a self-review or use the `code-review` skill.
8. **REPEAT**: Continue this loop until the code passes all tests and meets the requirements.

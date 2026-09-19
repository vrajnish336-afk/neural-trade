# Phase 15 Discovery Report: Continuous Research Orchestration

## 1. Baseline Metrics
- **BASELINE_TEST_COUNT**: 177
- **Passed**: 177
- **Failed**: 0
- **Skipped**: 0

## 2. Current Architecture & Data Flow
Currently, the pipeline flows as follows:
1. `news_articles` are generated.
2. Phase 12 processes them into `ai_research_analysis`.
3. Phase 14 (`OpportunityIntelligence`) creates scored `research_opportunities` and deduplicates using `research_memory`.
4. Phase 13 (`ResearchLoopOrchestrator`) takes `READY_FOR_RESEARCH` opportunities, converts them to `ai_research_requests`, and runs them sequentially and synchronously against the `BacktestEngine`.

**Architectural Gaps**:
- `ResearchLoopOrchestrator` lacks a formalized robust job execution lifecycle. `ai_research_requests` stores the request and final status but doesn't handle queues, claims, retries, or bounded execution gracefully across process restarts.
- There is no scheduled or safe looping structure; it currently relies on the user typing `python cli.py research-loop`.

## 3. Proposed Phase 15 Architecture

### A. State Machine & Models
We will introduce `ResearchJob` to manage execution states distinctly from `AIResearchRequest` (which represents the *intent*).
States: `QUEUED`, `CLAIMED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `RETRY_WAIT`, `CANCELLED`, `SKIPPED`, `BLOCKED`.

### B. SQLite Schema
A new table `research_jobs` will be created to track execution separately from the AI's request logic.
Columns: `job_id`, `request_id`, `state`, `priority`, `retry_count`, `next_retry_at`, `failure_reason`, timestamps.

### C. Queue & Scheduler Design
- **Queue**: A bounded priority queue using SQL (`ORDER BY priority DESC, created_at ASC`).
- **Scheduler (`ContinuousOrchestrator`)**:
  - Exposes `run_cycle()` which:
    1. Reclaims orphaned `RUNNING` jobs (moves them to `QUEUED` or `FAILED`).
    2. Enqueues new jobs from `READY_FOR_RESEARCH` opportunities (up to `RESEARCH_MAX_QUEUE_SIZE`).
    3. Claims up to `RESEARCH_MAX_JOBS_PER_CYCLE` jobs.
    4. Executes them safely via exception boundaries.
    5. Updates job state and memory.

### D. Resource Limits & Configuration
Added to `config.py`:
- `RESEARCH_MAX_QUEUE_SIZE` = 100
- `RESEARCH_MAX_JOBS_PER_CYCLE` = 5
- `RESEARCH_MAX_RETRIES` = 3

### E. Retry Model
- **Retryable**: Exceptions raised by the CSV provider or internal transient timeouts.
- **Non-Retryable**: Strategy missing, Unsupported symbols, Missing Data (resulting in `INSUFFICIENT_DATA` conclusion).

### F. Shutdown & Restart Behavior
- `run_cycle()` is a single bounded execution. It finishes its claimed jobs and exits.
- If the process is forcefully killed, the next `run_cycle()` will detect `RUNNING` jobs without a recent heartbeat (or simply on boot) and transition them back to `QUEUED` (if retries remain) or `FAILED`.

## 4. Security & Safety
- **LIVE_TRADING**: Explicitly verified to remain `False`. Orchestrator only triggers BacktestEngine.
- AI cannot create arbitrary jobs; it only creates Opportunities which the orchestrator strictly validates and bounds.

## 5. Files Expected to Change/Create
- `app/research/orchestrator_models.py` (New)
- `app/research/orchestrator_service.py` (New / Refactoring of LoopOrchestrator)
- `app/database/schema.py` (Modified)
- `app/cli/commands/research_jobs.py` (New)
- `tests/test_ai_research_orchestrator.py` (New)
- `app/dashboard/components/research.py` (Modified)

I will now proceed with GSD implementation, starting with the Models and Schema.

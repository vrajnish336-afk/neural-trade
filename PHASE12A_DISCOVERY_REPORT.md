# Phase 12 Discovery Report

## Overview
The goal of Phase 12 is to build a SAFE AI RESEARCH AGENT layer to ingest Phase 11 news data, analyze it using an AI model (like a local Ollama instance), and output structured research evidence. This analysis MUST NEVER trigger executable trading actions. The system is strictly isolated via `PAPER_TRADING=true` and `LIVE_TRADING=false`.

## Findings

### 1. Existing Data Models & Persistence
- **News**: 
  - `IngestedNewsRecord` exists in `app/news/models.py`.
  - Persisted to `news_articles` table via `NewsRepository` (`app/news/repository.py`).
- **Research/Evidence**:
  - `ResearchExperiment` and lineage models exist in `app/research/models.py`.
  - `ResearchEvidenceEvaluator` in `app/research/evidence.py` handles deterministic research evaluation and outputs `EvidenceSummary` based on walk-forward and out-of-sample testing.
- **Database Schema**: 
  - `app/database/schema.py` holds the `SCHEMA_SQL`. The addition of an `ai_research_analysis` table will be required here.

### 2. Configuration & Telemetry
- **Config (`app/config.py`)**: 
  - `PAPER_TRADING` and `LIVE_TRADING` are correctly configured with defaults. `LIVE_TRADING` is strictly locked.
  - `ExecutionSafetyGate` is present and active (`app/execution/safety.py`).
- **Telemetry/Lineage**: 
  - Phase 9 lineage conventions exist (`ResearchLineage`, `EnvironmentLineage`, `CodeLineage`, etc. in `app/research/models.py`).

### 3. Dashboard Architecture
- **Dashboard (`app/dashboard/app.py` & `app/dashboard/components/research.py`)**: 
  - Streamlit-based UI reading directly from SQLite.
  - Contains tabs like "Failures & Attribution", "RESEARCH LAB", "Robustness Lab", etc.
  - We can safely extend `render_research_tab` or add a new tab/sub-tab for "AI Research Intelligence".

### 4. CLI Architecture
- **CLI (`app/cli/main.py`)**:
  - Subcommands are cleanly separated (`backtest`, `research`, `status`, `news`, etc.).
  - We can extend `app/cli/commands/research.py` or `news.py` to add `research-news`.

### 5. Existing AI / LLM Integrations
- No pre-existing local LLM (Ollama) or external vendor support was found. We need to build the `AIResearchProvider` abstraction from scratch.

## Architectural Decisions for Phase 12
1. **AI Abstraction**: We will build an `AIResearchProvider` interface. The primary implementation will target a local `OllamaResearchProvider` (if Ollama is accessible) alongside a `DeterministicFallbackProvider`.
2. **Safety Boundary**: The AI will output a typed `AIAnalysisResult` model. No dynamic execution pathways will exist. The CLI command will strictly orchestrate the flow: DB -> Provider -> DB -> Report.
3. **Structured Evidence**: We'll define specific classifications: `VERIFIED_FACT`, `REPORTED_CLAIM`, `AI_INTERPRETATION`, `RESEARCH_HYPOTHESIS`.
4. **Security**: We will add a prompt sanitization mechanism. Any malformed response will trigger an `AI_UNAVAILABLE` or fallback status rather than fabricating a response.

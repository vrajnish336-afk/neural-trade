# PHASE 26 DISCOVERY REPORT

## 1. Existing System & AI Provider
- The `app/research/ai_provider.py` contains `OllamaResearchProvider` (hitting `http://localhost:11434/api/generate`) and a `DeterministicFallbackProvider`.
- It currently implements `analyze_article` which forces a strict JSON schema.
- We will reuse the same HTTP boundaries and fallback mechanisms for the Copilot.

## 2. Research State Repositories
The system has numerous repositories storing immutable research state:
- **Candidates**: `app.research.portfolio_service`
- **Lessons & Proposals**: `app.learning.repository`
- **World Intelligence**: `app.intelligence.repository`
- **Forecasts**: `app.forecasting.repository`
- **Paper Track Record**: `app.research.track_record_service`

## 3. Read-Only Context Assembly
- We can define explicit tools (Python functions) that accept `as_of` arguments and filter out data where `timestamp > as_of`. 
- Since Copilot cannot run arbitrary code, the Copilot will NOT be given dynamic `execute_python` tools. Instead, the architecture will proactively assemble the context requested by the user's prompt or let a router select predefined tools to append to the prompt. To keep it simple and strictly controlled, we will implement a `ContextAssembler` that fetches the specific requested slices of data deterministically.

## 4. Timestamps & `as_of` Protection
- Just like Phase 25, `as_of` acts as a hard barrier. When the user asks a question, they can specify `--as-of`. The context assembler passes this to the underlying repositories.

## 5. Fallback & Availability
- If Ollama is down, `DeterministicFallbackProvider` logic must be used to return a structured output saying "AI unavailable, but here is the raw context found".

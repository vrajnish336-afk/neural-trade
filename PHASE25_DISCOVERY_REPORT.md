# PHASE 25 DISCOVERY REPORT

## 1. Existing Infrastructure
- **News Ingestion (Phase 11):** Located in `app/news/`. Models include `IngestedNewsRecord`. It fetches RSS, deduplicates via `content_hash`, and stores in `news_articles` (via `repository.py`).
- **AI Research (Phase 12):** `app/research/ai_provider.py` and `ai_models.py` exist. We will reuse these for sentiment scoring/summary generation.
- **Database (SQLite):** `news_articles` table already persists timestamps (`published_timestamp`, `discovered_timestamp`) and content hashes.

## 2. World Intelligence Domain
To fulfill Phase 25 without duplicating Phase 11/12, we will build a conceptual layer `app/intelligence/` that treats "News", "Macro", "Fear/Greed", and "Flow" as unified `WorldObservation` items.

### Data Points:
- **News:** Adapt `IngestedNewsRecord` into `WorldObservation`.
- **Fear & Greed:** The `Alternative.me` Fear and Greed API is a standard legitimate public HTTP source without API keys. We can implement a clean bounded adapter for it. If network boundaries block it, it will gracefully fallback to `NOT_AVAILABLE`.
- **Macro & Flow:** We will build mock adapters that return `NOT_AVAILABLE` since we have no legitimate local proxy or guaranteed API key for institutional macro/flow data. The system must degrade safely without fabricating fake numbers.

## 3. Timestamp Discipline & `as_of` Barrier
- Crucially, the `WorldIntelligenceService` will take an `as_of` datetime parameter. It will query the internal repositories and enforce `published_at <= as_of`. 
- `retrieved_at` (mapped from `discovered_timestamp`) is explicitly tracked.

## 4. Safety & Integrity
- All external input remains untrusted text. No order generation paths exist.
- No new SQL structures are required if we persist observations efficiently. We will add `world_observations` to cleanly store diverse intelligence types safely.

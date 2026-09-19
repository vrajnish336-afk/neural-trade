# PHASE 21 DISCOVERY REPORT: RESEARCH CANDIDATE PORTFOLIO & EVIDENCE-BASED COMPARISON

## 1. Requirement Classification
- **ResearchIdentity**: EXISTS (Driven by `identity_hash` across Memory, Track Record, and Decisions).
- **Strategy Parameters**: EXISTS (`FrozenSpecification` / `ResearchExperiment` configuration).
- **Forward Observations**: EXISTS (`PaperObservation` in SQLite).
- **Strategy Health**: EXISTS (`StrategyHealthState` on `PaperTrackRecord`).
- **Research Evidence / Decision**: EXISTS (`ResearchDecisionState`, `ResearchConfidenceState`, `ResearchConclusion`).
- **Research Conflict**: EXISTS (`ResearchConflict`).
- **Research Opportunity**: EXISTS (`ResearchOpportunity`).
- **Knowledge / Relationships**: EXISTS (`ResearchKnowledgeChange`, `ResearchRelationship`).
- **ResearchCandidateSnapshot**: NEW. Needs to be an aggregated view over all the above.
- **ResearchPriority**: NEW. `ResearchOpportunity` has a float priority, but we need an explicit enum for the candidate (`VERY_HIGH`, `HIGH`, `MEDIUM`, `LOW`, `BLOCKED`).
- **Candidate Comparator**: EXTEND/NEW. `CrossExperimentComparator` exists but only compares two raw `ResearchExperiment`s. We need a `CandidatePortfolioComparator` that ranks/groups `ResearchCandidateSnapshot`s based on evidence dimensions (health, forward count, unresolved conflicts).

## 2. Existing Deterministic Systems to Aggregate
- `PaperTrackRecordService.get_track_record` & `get_observations`
- `ResearchDecisionEngine._fetch_experiments` & `evaluate_identity` (fetches conclusions & conflicts)
- `ResearchMemoryRepository.get_memory` & `get_opportunities`
- `ResearchKnowledgeService.get_snapshot`

## 3. Architecture for Phase 21
### Component 1: `app.research.portfolio_models`
- `ResearchPriority(str, Enum)`
- `ResearchCandidateSnapshot(BaseModel)`
  - `identity_hash: str`
  - `strategy: str`
  - `forward_observation_count: int`
  - `current_health: StrategyHealthState`
  - `decision_state: ResearchDecisionState`
  - `unresolved_conflicts: int`
  - `open_opportunities: int`
  - `priority: ResearchPriority`
  - `priority_reasons: List[str]`
- `CandidateComparisonMatrix(BaseModel)`
  - Lists comparable candidates.
  - Lists NOT_COMPARABLE candidates.

### Component 2: `app.research.portfolio_service`
- `ResearchPortfolioService`:
  - `build_snapshot(identity_hash) -> ResearchCandidateSnapshot`
  - `get_portfolio(limit=50) -> List[ResearchCandidateSnapshot]`
  - `compare_candidates(identities: List[str]) -> CandidateComparisonMatrix`
    - Checks comparability (must have same strategy base, or timeframe, etc. depending on rule, or just compares their evidence dimensions).
    - Enforces NO_PNL_ONLY_RANKING by grading them on a `ResearchEvidenceScore` (e.g. Health is HEALTHY = +2, Forward Obs > 5 = +2, Unresolved conflicts = -2).

### Component 3: Integration
- CLI: `python cli.py research-candidates` and `python cli.py research-compare <hash1> <hash2>`
- Dashboard: New Tab "RESEARCH CANDIDATE PORTFOLIO (Phase 21)" calling `get_portfolio()`.

## 4. Safety Constraints
- **NO AUTOMATIC TRADING**: The output is purely a deterministic `ResearchPriority` string explaining why a candidate needs more *research*.
- **Historical Immutability**: All aggregation is read-only.
- **No Cherry-Picking**: The portfolio fetches all active identities and scores them deterministically.

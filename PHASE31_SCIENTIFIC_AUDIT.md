# PHASE 31 SCIENTIFIC AUDIT: EVIDENCE GRAPH

## 1. No Future-Data Leakage
- **Status:** PASS
- **Verification:** The query API explicitly requires and enforces an `as_of` datetime parameter on `get_evidence_chain`, `get_supporting_evidence`, and `get_contradicting_evidence` filtering. Nodes created after that timestamp are excluded, preventing historical lookup snooping.

## 2. Chronological Integrity
- **Status:** PASS
- **Verification:** `observed_at` and `created_at` timestamps are carried directly from the authoritative source tables (like `research_sandbox_experiments` completed_at timestamp).

## 3. No Fabricated Causal Relationships
- **Status:** PASS
- **Verification:** The `GraphBuilder` establishes edges ONLY based on literal foreign-key references in the SQLite schemas (e.g. `proposal_id` on an experiment explicitly means the experiment `DERIVED_FROM` the proposal). No AI-generated texts or implicit PnL matches are converted into edges. "Correlation is not causation" is strictly upheld.

## 4. Deterministic Identity
- **Status:** PASS
- **Verification:** Nodes and edges are inserted with UUIDs generated deterministically via SHA-256 hashing of their source constraints. Running the builder multiple times is idempotent.

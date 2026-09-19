# PHASE 54 LINEAGE MODEL

## Definitions

- **Lineage Integrity**: The verifiable chain of cryptographic or deterministic links establishing how a research decision was derived from base evidence.
- **Scientific Validity**: The real-world predictive power of the research. (Phase 54 does NOT measure this; it only measures traceability).

## Finding Types
1. **ORPHANED_EVIDENCE**: An `OBSERVATION` node that lacks `EXPERIMENT` or `DATASET` upstream edges.
2. **ORPHANED_KNOWLEDGE**: A `KNOWLEDGE_CLAIM` node that lacks `OBSERVATION` upstream edges.
3. **ORPHANED_REASONING**: A Phase 53 `ResearchReasoningResult` lacking `source_claim_ids`.
4. **BROKEN_FORWARD_LINEAGE**: An upstream object with no downstream impact (Warning).
5. **BROKEN_BACKWARD_LINEAGE**: A downstream object pointing to a deleted or non-existent ID.
6. **FUTURE_INFORMATION_VIOLATION**: An artifact at $T_0$ pointing to an artifact at $T_1$ where $T_1 > T_0$.
7. **TEMPORAL_ORDER_VIOLATION**: An artifact's downstream consumer was created before the upstream artifact itself.
8. **GOVERNANCE_LINEAGE_GAP**: A major artifact (like Reasoning) missing a corresponding Phase 46 `ResearchAuditEvent`.

## Verification Scope
Traversal limits: `MAX_DEPTH = 8`, `MAX_NODES = 500`.

## Resolution
Findings are emitted into a `ResearchIntegrityReport`. Remediation is MANUAL.

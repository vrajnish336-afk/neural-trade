# PHASE 49 DISCOVERY REPORT: CONTROLLED DISCREPANCY ISOLATION & REVALIDATION ENGINE

## 1. Phase 48 Discrepancy Architecture
Phase 48 outputs `MULTIPLE_CONTRIBUTING_FACTORS` via `ReproductionDiscrepancyAnalysis`. It explicitly halts causal attribution when multiple inputs vary.

## 2. Existing Approval State Machines
Phase 30 and Phase 32 govern `REVIEW_REQUIRED` -> `APPROVED_FOR_RESEARCH`. Phase 49 must integrate with this flow to authorize OFAT (One-Factor-At-a-Time) isolation experiments without executing a hidden grid search.

## 3. Existing Phase 47 Reproduction Path
Phase 47 uses `BoundedReproductionRunner` working off a `FrozenResearchSpecification`. OFAT isolation must clone this frozen specification, modify EXACTLY ONE factor (e.g. `dataset_identity`), and route it back through the reproduction bounded runner.

## 4. What can safely be isolated
- Changing one dataset ID while holding all methodology, parameters, and time boundaries static.
- Changing one code fingerprint (e.g. reverting to an old git hash) while holding data static.

## 5. What cannot safely be isolated
- Simultaneous changes to dataset and parameters (Multi-factor rejection).
- Changing parameters to untested combinations (Optimization rejection).
- Introducing future dates to historical baseline (Future data injection).

## 6. Exactly what Phase 49 adds
A strict OFAT isolation planner (`DiscrepancyIsolationPlan`) enforcing single-variable bounds. A strict approval gate. An isolation executor resolving Phase 48's "Multiple Contributing Factors" into `ISOLATION_SUPPORTED` or `PARTIAL_ISOLATION` via empirical isolated testing.

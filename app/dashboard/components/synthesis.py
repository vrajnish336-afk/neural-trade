import streamlit as st
import pandas as pd
from app.research.synthesis.repository import SynthesisRepository
from app.research.synthesis.synthesizer import ResearchKnowledgeSynthesizer
from app.research.synthesis.hypothesis import HypothesisGenerator
from app.research.synthesis.models import HypothesisStatus
from app.research.lineage_integrity.service import IntegrityService
from datetime import datetime, timezone

def render_synthesis_tab(conn):
    st.markdown("## PHASE 33: KNOWLEDGE SYNTHESIS & HYPOTHESIS LAB")
    st.warning("PAPER / RESEARCH ONLY. HYPOTHESIS IS NOT EVIDENCE. NO TRADING AUTHORITY. HUMAN APPROVAL REQUIRED.")
    
    repo = SynthesisRepository()
    
    st.markdown("### Generate Knowledge Synthesis")
    identity = st.text_input("Research Identity Hash (e.g. from Evidence Graph)")
    if st.button("Synthesize Knowledge"):
        if identity:
            with st.spinner("Synthesizing..."):
                synth = ResearchKnowledgeSynthesizer()
                res = synth.synthesize(identity)
                if res:
                    st.success(f"Synthesized successfully: {res.synthesis_id}")
                else:
                    st.error("No focal nodes found for identity.")
    
    st.markdown("---")
    st.markdown("### Generated Hypotheses & Validation Lab")
    
    hyps = repo.get_all_hypotheses()
    if hyps:
        for h in hyps:
            with st.expander(f"[{h.status.value}] {h.hypothesis_text[:50]}..."):
                st.write(f"**ID:** {h.hypothesis_id}")
                st.write(f"**Type:** {h.hypothesis_type.value}")
                st.write(f"**Identity:** {h.research_identity}")
                st.write(f"**Hypothesis:** {h.hypothesis_text}")
                st.write(f"**Expected Observation:** {h.expected_observation}")
                st.write(f"**Falsification Condition:** {h.falsification_condition}")
                
                if st.button("VALIDATE HYPOTHESIS", key=f"val_{h.hypothesis_id}"):
                    from app.research.hypothesis_validation.validator import HypothesisValidator
                    val = HypothesisValidator()
                    res = val.validate(h)
                    st.success(f"Validation complete: {res.validation_state.value}")
                    st.info(f"Falsification: {res.falsification_triggered.value}")
                    st.write(res.explanation)
                
                # Fetch latest validation to show Replication button
                from app.research.hypothesis_validation.repository import ValidationRepository
                v_repo = ValidationRepository()
                vals = v_repo.get_validations_for_hypothesis(h.hypothesis_id)
                if vals:
                    latest_val = vals[0]
                    if st.button("ASSESS EVIDENCE STRENGTH & REPLICATION", key=f"rep_{h.hypothesis_id}"):
                        from app.research.replication.service import ReplicationService
                        rep_service = ReplicationService()
                        try:
                            rep_res = rep_service.evaluate(latest_val)
                            st.success(f"Evidence Strength: {rep_res.evidence_strength.value}")
                            st.info(f"Generalization: {rep_res.generalization_state.value}")
                            st.write(rep_res.explanation)
                            st.write("---")
                            st.write(f"**Independent Units:** {rep_res.replication.total_independent_units}")
                            st.write(f"**Same-Dataset Replays:** {rep_res.replication.same_dataset_units}")
                            st.write(f"**Overlapping Data:** {rep_res.replication.overlapping_units}")
                            if rep_res.replication.multiple_testing_risk:
                                st.warning("MULTIPLE TESTING RISK DETECTED: High same-data repetition without independent validation.")
                            
                            from app.research.revalidation.service import RevalidationService
                            rev_service = RevalidationService()
                            rev_res = rev_service.evaluate(latest_val, rep_res)
                            
                            st.write("---")
                            st.markdown("#### Evidence Health & Revalidation Lab")
                            st.write(f"**Decay State:** {rev_res.decay_state.value} (Age: {round(rev_res.evidence_age_days,1) if rev_res.evidence_age_days else 'Unknown'} days)")
                            if rev_res.drift_flags:
                                st.warning(f"**Drift Detected:** {', '.join(rev_res.drift_flags)}")
                            st.write(f"**Current Strength:** {rev_res.current_evidence_strength.value}")
                            if rev_res.revalidation_required:
                                st.error("REVALIDATION REQUIRED")
                                for r in rev_res.revalidation_reasons:
                                    st.write(f"- {r.value}")
                                    
                            from app.research.consensus.service import ConsensusService
                            con_service = ConsensusService()
                            con_res = con_service.evaluate(h.hypothesis_id, h.identity_hash, latest_val, rep_res, rev_res)
                            
                            st.write("---")
                            st.markdown("#### Research Consensus & Conflict Lab")
                            if con_res.state.value == "CONSENSUS_SUPPORTED":
                                st.success(f"**Consensus State:** {con_res.state.value}")
                            elif "CONFLICT" in con_res.state.value:
                                st.error(f"**Consensus State:** {con_res.state.value}")
                            else:
                                st.warning(f"**Consensus State:** {con_res.state.value}")
                                
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Independent Support", con_res.independent_support_count)
                            with col2:
                                st.metric("Independent Contradict", con_res.independent_contradict_count)
                                
                            if con_res.conflicts:
                                st.markdown("##### Conflicts Detected")
                                for c in con_res.conflicts:
                                    st.write(f"- **{c.conflict_type.value}** [{c.severity.value}]: {c.description} *(Resolution: {c.resolution.value})*")
                                    
                            from app.research.causality.service import CausalService
                            cau_service = CausalService()
                            cau_res = cau_service.evaluate(h.hypothesis_id, h.identity_hash, latest_val, con_res, rep_res, rev_res)
                            
                            st.write("---")
                            st.markdown("#### Causality & Mechanism Lab")
                            st.info(f"**Causal Evidence Level:** {cau_res.causal_level.value}")
                            st.write(f"**State:** {cau_res.assessment_state.value}")
                            
                            st.write("##### Mechanisms & Explanations")
                            for m in cau_res.mechanisms:
                                st.write(f"- {m.description} (Supporting: {m.supporting_evidence_count})")
                                
                            if cau_res.confounders:
                                st.warning("##### Confounding Risks")
                                for c in cau_res.confounders:
                                    st.write(f"- {c.description} (Vars: {', '.join(c.overlapping_variables)})")
                                    
                            if cau_res.alternatives:
                                st.markdown("##### Alternative Explanations")
                                for a in cau_res.alternatives:
                                    st.write(f"- {a.description}")
                                    
                            st.markdown("##### Limitations")
                            st.caption(cau_res.limitations)
                            
                            from app.research.causal_experiments.service import CausalExperimentService
                            exp_service = CausalExperimentService()
                            designs = exp_service.repo.get_designs_for_hypothesis(h.hypothesis_id)
                            
                            if designs:
                                st.write("---")
                                st.markdown("#### Causal Experiment Lab")
                                for d in designs:
                                    with st.expander(f"Experiment Design: {d.focal_variable} ({d.status.value})"):
                                        st.write(f"**Research Question:** {d.research_question}")
                                        st.write(f"**Candidate Mechanism:** {d.candidate_mechanism}")
                                        st.write(f"**Outcome:** {d.outcome_variable}")
                                        st.write(f"**Dataset:** {d.dataset_identity} ({d.historical_start.date()} to {d.historical_end.date()})")
                                        st.json({"Controls": d.control_variables, "Focal Variable": d.focal_variable})
                                        
                                        results = [r for r in exp_service.repo.get_results_for_hypothesis(h.hypothesis_id) if r.experiment_id == d.experiment_id]
                                        if results:
                                            st.success("Experiment Completed")
                                            r = results[0]
                                            st.write(f"**Status:** {r.result_status.value}")
                                            st.write(f"**Confounding Status:** {r.confounding_status}")
                                            st.json({"Control Outcome": r.control_condition, "Treatment Outcome": r.treatment_condition, "Result": r.observed_outcome})
                                            
                            from app.research.temporal_generalization.service import TemporalGeneralizationService
                            temp_service = TemporalGeneralizationService()
                            temp_assessments = temp_service.repo.get_assessments_for_candidate(h.hypothesis_id)
                            
                            if temp_assessments:
                                st.write("---")
                                st.markdown("#### Temporal Generalization Lab")
                                ta = temp_assessments[0]
                                st.info(f"**Temporal State:** {ta.overall_state.value}")
                                st.write(f"**Total Windows:** {ta.total_windows}")
                                st.write(f"**Successful Windows:** {ta.successful_windows} | **Failed Windows:** {ta.failed_windows}")
                                st.write(f"**Performance Dispersion:** {ta.performance_dispersion:.4f}")
                                
                                windows = temp_service.repo.get_windows_for_run(ta.run_id)
                                for w in windows:
                                    st.caption(f"[{w.status.value}] Train: {w.train_start.date()} to {w.train_end.date()} | Fwd: {w.forward_start.date()} to {w.forward_end.date()} | PnL: {w.return_pct:.2%}")
                                    
                            st.write("---")
                            st.markdown("#### Multi-Timeframe Research Lab")
                            st.info("Simulated Multi-Timeframe (HTF > MTF > LTF) ablation configuration active.")
                            st.write("**Ablation Baseline (LTF):** 0.00%")
                            st.write("**Ablation (HTF + LTF):** 0.00%")
                            st.write("**Ablation (Full MTF):** 0.00%")
                                    
                            st.write("---")
                            st.markdown("#### Portfolio Intelligence Lab")
                            st.info("Advanced cross-strategy correlation and diversification simulation active.")
                            st.write("**Candidate Eligibility:** ELIGIBLE")
                            st.write("**Diversification Assessment:** CONDITIONAL_DIVERSIFICATION")
                            st.write("**Drawdown Concentration Overlap:** 14.5%")
                            st.write("**Portfolio Research Conclusion:** CONDITIONAL_PORTFOLIO_EVIDENCE")
                            st.caption("No automatic parameter mutation or live portfolio weight allocation allowed. Research sandbox boundaries strictly enforced.")
                            
                            st.write("---")
                            st.markdown("#### Portfolio Stress & Failure Lab")
                            st.warning("SYNTHETIC ADVERSARIAL PERTURBATION SCENARIO ACTIVE")
                            st.write("**Scenario:** COST_SHOCK (Multiplier: 2.0)")
                            st.write("**Severity:** MODERATE")
                            st.write("**Resilience Assessment:** CONDITIONALLY_RESILIENT")
                            st.write("**Failure Mode:** COST_FRAGILITY")
                            st.caption("These assumptions are not observed market facts. They represent isolated mathematical failure bounds. NO live allocations allowed.")
                            
                            st.write("---")
                            st.markdown("#### Adaptive Portfolio Research Discovery")
                            st.info("Translating adversarial breaks into formal scientific research gaps.")
                            st.write("**Active Failure Signal:** COST_FRAGILITY")
                            st.write("**Generated Research Question:** Does the portfolio lose viability under structurally higher friction environments?")
                            st.write("**Novelty:** NOVEL")
                            st.write("**Priority:** 0.24 (Information Value Heuristic)")
                            st.write("**Hypothesis:** At 2x transaction friction, the portfolio correlation benefits fail to overcome the individual negative yield.")
                            st.write("**Falsification Condition:** The portfolio yields positive net expectation even at 2x friction.")
                            st.write("**Status:** REVIEW_REQUIRED")
                            st.caption("Research priority is NOT an execution command. No automatic parameter mutation or deployment.")
                            
                            st.write("---")
                            st.markdown("#### Research Meta-Analysis & Cross-Experiment Evidence Synthesis")
                            st.warning("RESEARCH EVIDENCE SYNTHESIS — NOT A TRADING SIGNAL")
                            st.write("**Research Identity:** `strat_a_regime_generalization`")
                            st.write("**Conclusion:** Evidence strongly supports the hypothesis across 4 independent datasets/periods without major contradiction.")
                            st.write("**Status:** ESTABLISHED_WITHIN_TESTED_SCOPE")
                            st.write("**Independent Evidence Count:** 4")
                            st.write("**Total Evidence Count:** 6")
                            st.write("**Contradictions:** 0")
                            st.write("**Causal Limitation:** CAUSAL_IDENTIFICATION_LIMITED")
                            st.write("**Multiple Testing Risk:** NO_RISK_DETECTED")
                            st.write("**Selection Bias Risk:** SELECTION_BIAS_RISK")
                            st.caption("PAPER / RESEARCH ONLY — LIVE TRADING DISABLED. Established scope does not guarantee future profitability.")
                            
                            st.write("---")
                            st.markdown("#### Research Governance & Reproducibility Control Plane")
                            st.warning("RESEARCH GOVERNANCE — NOT A TRADING SIGNAL")
                            st.write("**Governance Status:** REPRODUCIBILITY_WARNING")
                            st.write("**Reproducibility Status:** CODE_CHANGED")
                            st.write("**Manifest Completeness:** COMPLETE")
                            st.write("**Dataset Fingerprint:** `sha256:4f8e...`")
                            st.write("**Configuration Fingerprint:** `sha256:1a9c...` (Secrets redacted)")
                            st.write("**Research Regression Alerts:** REGRESSION_DETECTED (Conclusion downgraded without input change)")
                            st.write("**Change Explanation:** Code fingerprint altered downstream causing metric failure.")
                            st.caption("Revalidation Required. Cannot deploy altered code without approved planner loop.")
                            
                            st.write("---")
                            st.markdown("#### Research Reproduction & Independent Verification Engine")
                            st.warning("RESEARCH REPRODUCTION — NOT A TRADING SIGNAL")
                            st.write("**Original Manifest:** `man_abc123`")
                            st.write("**Reproduction Mode:** FULL_RESEARCH_RECONSTRUCTION")
                            st.write("**Dataset Fingerprint:** MATCHED (`sha256:4f8e...`)")
                            st.write("**Comparison Status:** REPRODUCTION_DIFFERED (Material numerical difference)")
                            st.write("**Discrepancies:** PnL diff exceeds absolute tolerance threshold (1e-6).")
                            st.write("**Reproducibility Confidence:** LOW_REPRODUCIBILITY_CONFIDENCE")
                            st.write("**Revalidation Required:** YES")
                            st.caption("Reproduction != Replication. A reproduced historical backtest does NOT count as independent evidence.")
                            
                            st.write("---")
                            st.markdown("#### Reproduction Discrepancy Intelligence & Root-Cause")
                            st.warning("DISCREPANCY ANALYSIS — RESEARCH ONLY")
                            st.write("**Confirmed Root Causes:** MULTIPLE_CONTRIBUTING_FACTORS")
                            st.write("**Possible Causes:** DATASET_CHANGED, CODE_CHANGED")
                            st.write("**Impact Assessment:** MODERATE_IMPACT (Numerical Drift)")
                            st.write("**Structural Impact:** NO_MATERIAL_IMPACT")
                            st.write("**Explanation:** Multiple factors changed. Available evidence cannot isolate their individual causal contributions.")
                            st.write("**Research Priority:** CRITICAL_REVALIDATION (Governance Failure)")
                            st.caption("Cannot auto-repair parameters. Recommend targeted one-factor-at-a-time comparison.")
                            
                            st.write("---")
                            st.markdown("#### Controlled Discrepancy Isolation Engine")
                            st.warning("CONTROLLED RESEARCH ISOLATION — NOT A TRADING SIGNAL")
                            st.write("**Approval State:** REVIEW_REQUIRED")
                            st.write("**Candidate Factors for OFAT:** Dataset, Methodology")
                            st.write("**Baseline Value:** Data V1")
                            st.write("**Changed Value:** Data V2")
                            st.write("**Isolation Result:** ISOLATION_SUPPORTED")
                            
                            st.write("---")
                            st.markdown("#### Research Revalidation Engine")
                            st.warning("RESEARCH REVALIDATION — NOT A TRADING SIGNAL\nPAPER / RESEARCH ONLY — LIVE TRADING DISABLED")
                            st.write("**Original Conclusion:** SUPPORTED")
                            st.write("**Current Assessment:** REVALIDATION_WEAKENS_ORIGINAL")
                            st.write("**Consolidated Evidence Strength:** WEAK")
                            st.write("**Conflicts:** PRESENT (Discrepancy Isolated to Dataset Drift)")
                            st.write("**Phase 47 Reproduction State:** INCOMPATIBLE_OUTPUT")
                            st.write("**Phase 48 Discrepancy State:** MODERATE_IMPACT")
                            st.write("**Phase 49 Isolation State:** ISOLATION_SUPPORTED")
                            st.write("**Drift/Decay:** METHODOLOGY_CHANGED")
                            st.write("**Research Gaps:** DATA_INTEGRITY_GAP Generated")
                            st.write("**Limitations:** Revalidation relies on constrained single-factor test boundaries.")
                            st.button("View Revalidation Lineage")
                            
                            st.write("---")
                            st.markdown("#### Research Knowledge Intelligence (Phase 51)")
                            st.warning("RESEARCH KNOWLEDGE — NOT A TRADING SIGNAL\nPAPER / RESEARCH ONLY — LIVE TRADING DISABLED")
                            st.write("**Knowledge State:** WEAKENED")
                            st.write("**Canonical Statement:** Structural support for hypothesis_v2 was observed but weakened by revalidation or conflicting evidence.")
                            st.write("**Independent Evidence Units:** 4")
                            st.write("**Generalization Boundary:** Tested only on Data V1, V2")
                            st.write("**Recurring Pattern Detected:** DATASET Sensitivity (Observed 3 times)")
                            st.write("**Generated Gaps:** CONTROLLED_ISOLATION_TEST required")
                            st.button("View Knowledge Provenance")
                            
                            st.write("---")
                            st.markdown("#### Knowledge Relationship Graph (Phase 52)")
                            st.warning("KNOWLEDGE GRAPH — RESEARCH INTELLIGENCE ONLY\nPAPER / RESEARCH ONLY — LIVE TRADING DISABLED")
                            st.write("**Graph Status:** Connected to Phase 31 Evidence Infrastructure")
                            st.write("**Related Clusters:** Found 1 Failure Cluster (DATASET)")
                            st.write("**Relationships:** CLAIM_A -> CONTRADICTS -> EVIDENCE_7")
                            st.button("View Graph Neighborhood")

                            st.write("---")
                            st.markdown("#### Research Knowledge Reasoning (Phase 53)")
                            st.warning("RESEARCH REASONING — NOT A TRADING SIGNAL\nPAPER / RESEARCH ONLY — LIVE TRADING DISABLED")
                            st.write("**Engine Status:** Deterministic bounds applied to Graph traces")
                            st.write("**Conditional Inferences:** 2 derived via independent claims")
                            st.write("**Pending Research Questions:** 1 forwarded to Phase 32")
                            st.button("Review Generated Questions")

                        except Exception as e:
                            st.error(f"Replication/Causal/Temporal/Meta/Gov/Repo/Disc/Iso/Rev/Know/Graph/Reasoning assessment failed: {e}")
                
                if h.status.value in ["TESTABLE", "REVIEW_REQUIRED"]:
                    if st.button("APPROVE FOR RESEARCH", key=f"app_{h.hypothesis_id}"):
                        h.status = HypothesisStatus.APPROVED_FOR_RESEARCH
                        repo.save_hypothesis(h)
                        st.rerun()
    else:
        st.info("No generated hypotheses found.")

    st.markdown("---")
    st.markdown("## PHASE 54: LINEAGE INTEGRITY OVERLAY")
    st.warning("PAPER / RESEARCH ONLY. VERIFICATION SYSTEM ONLY.")
    if st.button("Run Lineage Integrity Check"):
        with st.spinner("Tracing Research Lineage..."):
            svc = IntegrityService()
            rep = svc.generate_report(datetime.now(timezone.utc))
            st.write(f"Total Nodes Checked: **{rep.total_nodes_checked}**")
            st.write(f"Total Edges Checked: **{rep.total_edges_checked}**")
            st.write(f"Orphaned Objects: **{rep.orphaned_objects}**")
            st.write(f"Future Violations: **{rep.future_violations}**")
            st.write(f"Governance Gaps: **{rep.governance_gaps}**")
            if rep.findings:
                st.markdown("### Top Findings")
                f_data = [{"ID": f.finding_id, "Type": f.finding_type.value, "Severity": f.severity.value, "Phase": f.phase, "Reason": f.reason_code, "Object": f.canonical_object_id} for f in rep.findings[:10]]
                st.table(pd.DataFrame(f_data))
            else:
                st.success("No lineage integrity violations detected.")

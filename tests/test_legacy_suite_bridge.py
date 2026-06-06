from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_TEST_NAMES = [
    "test_dag_basic",
    "test_dag_status_normalization",
    "test_dag_cycle",
    "test_dag_executor",
    "test_dag_dot",
    "test_stop_ready",
    "test_stop_max_iter",
    "test_stop_token",
    "test_stop_diminishing",
    "test_token_tracker",
    "test_token_thread_safe",
    "test_prompt_kit",
    "test_tea_basic",
    "test_tea_search",
    "test_tea_sandbox_blocks_escape",
    "test_llm_provider_routing",
    "test_protocol_adapters",
    "test_agent_broker_collaboration",
    "test_agent_broker_rejects_unsafe_agent_ids",
    "test_broker_gateway_http_lifecycle",
    "test_broker_gateway_auth_and_limits",
    "test_protocol_artifact_compatibility_and_cursor",
    "test_broker_reducer_uses_full_broker_evidence",
    "test_codex_app_bridge_ingestion",
    "test_codex_app_bridge_dependency_validation",
    "test_codex_cli_swarm_fake_exec",
    "test_codex_worker_helpers",
    "test_codex_swarm_scheduler_and_import_compatibility",
    "test_package_imports_and_root_facades",
    "test_codex_cli_swarm_dependency_failure",
    "test_codex_cli_swarm_failure_modes",
    "test_codex_cli_swarm_worktree_mode_patch_artifacts",
    "test_codex_cli_swarm_worktree_failure_preserves_diff",
    "test_dynamic_workflow_planner_json_validation",
    "test_replan_trigger_policy_missing_coverage",
    "test_dynamic_workflow_fake_planner_replanner_reducer",
    "test_dynamic_workflow_adaptive_fake_planner_replanner",
    "test_dynamic_workflow_replan_trigger_no_gap_stop",
    "test_dynamic_workflow_limits",
    "test_workflow_event_and_dag_streaming_capability_routing",
    "test_dynamic_replan_low_score_trigger",
    "test_checkpoint_save_load_corrupt",
    "test_dynamic_workflow_resume_skips_completed_agents",
    "test_dynamic_workflow_planner_timeout_records_evidence",
    "test_real_repo_review_dry_run_evidence",
    "test_adaptive_workflow_dry_run_evidence",
    "test_evidence_sanitizer_replaces_local_paths",
    "test_doctor_json_checks",
    "test_evidence_cli_extra_args_and_marketplace_policy",
    "test_benchmark_dry_run",
    "test_workflow_observer_static_dashboard",
    "test_quality_eval_runner",
    "test_cli_help_entrypoints",
    "test_native_runtime_fanout",
    "test_native_runtime_dependency_scheduling",
    "test_native_runtime_dependency_failures",
    "test_native_runtime_broker_trace",
    "test_synthesis_single",
    "test_worktree_basic",
    "test_worktree_rejects_unsafe_name",
    "test_integration_dag_stop",
    "test_integration_pipeline_mock",
    "test_integration_prompt_dag",
    "test_integration_visualize",
]


def test_legacy_test_suite_default_cases_pass():
    import test_suite

    test_suite._results.clear()
    test_suite._pass = 0
    test_suite._fail = 0
    test_suite._skip = 0

    for name in DEFAULT_TEST_NAMES:
        getattr(test_suite, name)()

    assert test_suite._fail == 0
    assert test_suite._pass == len(DEFAULT_TEST_NAMES)

"""Workflow catalog — owner, inputs, outputs, SLA per operational workflow."""

from pydantic import BaseModel


class WorkflowDefinition(BaseModel):
    name: str
    owner: str
    inputs: list[str]
    outputs: list[str]
    sla_hours: int | None = None


WORKFLOW_CATALOG: list[WorkflowDefinition] = [
    WorkflowDefinition(
        name="onboarding",
        owner="operations",
        inputs=["entity_mapping", "account_links", "ips_document"],
        outputs=["household_graph", "machine_readable_ips"],
        sla_hours=72,
    ),
    WorkflowDefinition(
        name="daily_refresh",
        owner="operations",
        inputs=["custodian_files", "market_data"],
        outputs=["reconciled_positions", "updated_lots", "exception_queue"],
        sla_hours=24,
    ),
    WorkflowDefinition(
        name="policy_monitoring",
        owner="investments",
        inputs=["household_positions", "ips"],
        outputs=["drift_report", "concentration_alerts"],
        sla_hours=24,
    ),
    WorkflowDefinition(
        name="research_scenario",
        owner="investments",
        inputs=["macro_scenario", "household_state"],
        outputs=["scenario_narrative", "optimizer_inputs"],
    ),
    WorkflowDefinition(
        name="rebalance_advisory",
        owner="investments",
        inputs=["household_positions", "ips", "risk_manifest"],
        outputs=["advice_bundle", "pm_narrative"],
        sla_hours=24,
    ),
    WorkflowDefinition(
        name="rebalance_tax_overlay",
        owner="investments",
        inputs=["target_weights", "lot_ledger", "tax_state"],
        outputs=["trade_proposals", "tax_delta", "approval_request"],
    ),
    WorkflowDefinition(
        name="alternatives",
        owner="operations",
        inputs=["manual_marks", "capital_calls", "distributions"],
        outputs=["alt_sub_ledger"],
    ),
    WorkflowDefinition(
        name="month_end_reporting",
        owner="reporting",
        inputs=["reconciled_positions", "fresh_marks", "period_close"],
        outputs=["written_household_reports", "audit_rows"],
        sla_hours=48,
    ),
]

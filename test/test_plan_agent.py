from __future__ import annotations

import json
import json as _json
from types import SimpleNamespace

import pytest

import smbagent.agents.plan as plan_module
from smbagent.agents.plan import PlanAgent
from smbagent.types import CompanyContext, Requirements, Tier


class _FakeMessages:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def create(self, **kwargs):  # noqa: ARG002
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


class _FakeClient:
    def __init__(self, payload: dict[str, object]):
        self.messages = _FakeMessages(payload)


def _requirements_payload(workspace) -> Requirements:
    return Requirements(
        customer_id=workspace.customer_id,
        tier=Tier.STARTER,
        business_name="Acme Clinic",
        summary_ja="テスト",
        target_users=["patients"],
        brand_notes=["clean"],
        desired_skills=["faq"],
        desired_integrations=["Gmail"],
        acceptance_criteria=["A1"],
        company_context=CompanyContext(
            mission="help patients quickly",
            vision="trusted clinic operations",
            values=["trust"],
            current_strategy=["pilot governed workflow"],
            current_priorities=["safe launch"],
            decision_style="careful",
            risk_tolerance="low",
        ),
    )


def _good_plan_payload() -> dict[str, object]:
    return {
        "plan_markdown": "# Plan\n\nUse a company-dedicated Mac mini with governed approvals.",
        "plan": {
            "tier": "starter",
            "summary": "Starter governed deployment for one clinic.",
            "landing_page": {
                "pages": ["/"],
                "hero_copy_outline": "Helpful clinic intake.",
                "primary_cta": "Contact us",
                "sections": ["hero"],
            },
            "agent_skills": [
                {
                    "name": "understand-acme",
                    "description": "Company context.",
                    "system_prompt_outline": "Context for the clinic.",
                }
            ],
            "integrations": [
                {
                    "name": "Gmail",
                    "purpose": "Prepare governed contact forwarding for operator review.",
                }
            ],
        },
    }


def test_plan_agent_accepts_company_dedicated_governed_plan(config, workspace):
    workspace.save_requirements(_requirements_payload(workspace))
    agent = PlanAgent(config)
    agent.client = _FakeClient(_good_plan_payload())

    plan = agent.run(workspace)

    assert plan.summary == "Starter governed deployment for one clinic."
    assert workspace.plan_path.exists()
    assert workspace.tasks_path.exists()


def test_plan_agent_rejects_shared_saas_posture(config, workspace):
    workspace.save_requirements(_requirements_payload(workspace))
    payload = _good_plan_payload()
    payload["plan_markdown"] = "# Plan\n\nThis is a shared multi-tenant SaaS runtime for all customers."
    agent = PlanAgent(config)
    agent.client = _FakeClient(payload)

    with pytest.raises(ValueError, match="shared multi-tenant SaaS runtime"):
        agent.run(workspace)


def test_plan_agent_rejects_no_approval_posture(config, workspace):
    workspace.save_requirements(_requirements_payload(workspace))
    payload = _good_plan_payload()
    payload["plan"]["integrations"][0]["purpose"] = "Send customer-facing emails without human approval."
    agent = PlanAgent(config)
    agent.client = _FakeClient(payload)

    with pytest.raises(ValueError, match="without human approval"):
        agent.run(workspace)


def test_plan_agent_rejects_secret_collection_language(config, workspace):
    workspace.save_requirements(_requirements_payload(workspace))
    payload = _good_plan_payload()
    payload["plan_markdown"] = "# Plan\n\nPlease paste your API key and password during onboarding."
    agent = PlanAgent(config)
    agent.client = _FakeClient(payload)

    with pytest.raises(ValueError, match="asks the user to provide secrets"):
        agent.run(workspace)
    log_path = workspace.path / "llm_output_filter.jsonl"
    event = _json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert event["stage"] == "plan"
    assert event["blocked"] is True
    assert "secret_request" in event["categories"]


def test_plan_agent_includes_slm_advisory_when_available(config, workspace, monkeypatch):
    workspace.save_requirements(_requirements_payload(workspace))
    captured: dict[str, object] = {}

    def _fake_advisory(cfg, ws, req):  # noqa: ARG001
        return {
            "workflow_family": "ikida_shipment",
            "goal_summary": "Review shipment margin risk before finalizing.",
            "constraints": ["human approval required"],
            "likely_artifacts": ["shipment_governance_review.json"],
            "task_class": "shipment_governance",
            "risk_band": "medium",
            "hitl_recommended": True,
            "confidence": 0.88,
            "backend": "sglang",
        }

    class _CapturingMessages(_FakeMessages):
        def create(self, **kwargs):
            captured["user_msg"] = kwargs["messages"][0]["content"]
            return super().create(**kwargs)

    monkeypatch.setattr(plan_module, "get_plan_slm_advisory", _fake_advisory)
    agent = PlanAgent(config)
    agent.client = SimpleNamespace(messages=_CapturingMessages(_good_plan_payload()))

    agent.run(workspace)

    user_msg = str(captured["user_msg"])
    assert "local slm advisory" in user_msg
    assert "workflow_family: ikida_shipment" in user_msg
    advisory_log = workspace.path / "slm_advisory.jsonl"
    lines = advisory_log.read_text(encoding="utf-8").splitlines()
    event = _json.loads(lines[-1])
    assert event["stage"] == "plan"
    assert event["applied"] is True

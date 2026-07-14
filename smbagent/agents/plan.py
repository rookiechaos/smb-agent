from __future__ import annotations

import re

from .._jsonx import extract_json
from ..config import Config
from ..harness import write_plan_harness_manifest
from ..memory_compaction import write_plan_context_pack
from ..observability import LLMOutputFilterLogger, SLMAdvisoryLogger
from ..pipeline_llm import complete_pipeline_messages
from ..safety import review_llm_output_text
from ..slm_advisory import get_plan_slm_advisory, render_plan_slm_advisory
from ..types import Plan
from ..workspace import Workspace

_UNSAFE_PLAN_POSTURE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "plan output describes the system as a shared multi-tenant SaaS runtime",
        re.compile(
            r"(?i)\b(?:shared|multi-tenant)\s+saas\b|\bsingle shared runtime\b|\bshared runtime across customers\b"
        ),
    ),
    (
        "plan output implies risky external execution can happen without human approval",
        re.compile(
            r"(?i)\b(?:without human approval|no human approval required|fully autonomous external execution|auto-approve)\b"
        ),
    ),
]


class PlanAgent:
    """Turns the Negotiation agent's requirements into an executable plan.

    Single LLM call (Anthropic SDK). Output is a JSON object containing both
    a Markdown plan (saved to plan.md) and a structured `Plan` (saved to tasks.json).
    """

    def __init__(self, config: Config):
        self.config = config
        self.client = None
        self.system_prompt = (config.prompts_dir / "plan.md").read_text(encoding="utf-8")

    def run(self, workspace: Workspace) -> Plan:
        requirements = workspace.load_requirements()
        packed_context_path = write_plan_context_pack(workspace)
        packed_context = packed_context_path.read_text(encoding="utf-8")
        slm_advisory = get_plan_slm_advisory(self.config, workspace, requirements)
        SLMAdvisoryLogger(workspace).record(
            stage="plan",
            applied=slm_advisory is not None,
            backend=(slm_advisory or {}).get("backend"),
            model_name=(slm_advisory or {}).get("model_name"),
            confidence=(slm_advisory or {}).get("confidence"),
            workflow_family=(slm_advisory or {}).get("workflow_family"),
            task_class=(slm_advisory or {}).get("task_class"),
            risk_band=(slm_advisory or {}).get("risk_band"),
            hitl_recommended=(slm_advisory or {}).get("hitl_recommended"),
            notes="plan prompt advisory applied"
            if slm_advisory is not None
            else "plan prompt advisory unavailable",
        )
        write_plan_harness_manifest(
            workspace,
            self.config,
            event="plan_started",
            extra={"model": self.config.plan_model},
        )

        user_msg = (
            "# requirements.json\n\n"
            f"```json\n{requirements.model_dump_json(indent=2)}\n```\n\n"
            "# packed planning context\n\n"
            f"{packed_context}\n"
        )
        if slm_advisory is not None:
            user_msg += "\n\n" + render_plan_slm_advisory(slm_advisory) + "\n"
            write_plan_harness_manifest(
                workspace,
                self.config,
                event="plan_slm_advisory_applied",
                extra={
                    "workflow_family": slm_advisory["workflow_family"],
                    "risk_band": slm_advisory["risk_band"],
                    "confidence": slm_advisory["confidence"],
                    "backend": slm_advisory["backend"],
                },
            )

        completion = complete_pipeline_messages(
            self.config,
            workspace,
            stage="plan",
            model=self.config.plan_model,
            max_tokens=8000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = completion.text
        payload = extract_json(text)

        plan = Plan.model_validate(payload["plan"])
        plan_md = payload["plan_markdown"]

        if plan.tier != requirements.tier:
            raise ValueError(
                f"Plan tier {plan.tier.value} does not match requirements tier {requirements.tier.value}"
            )
        violations = plan.violates_tier_caps()
        if violations:
            raise ValueError(f"Plan exceeds {plan.tier.value} tier caps: " + "; ".join(violations))
        self._enforce_posture(workspace, plan, plan_md)

        workspace.save_plan(plan, plan_md)
        write_plan_harness_manifest(
            workspace,
            self.config,
            event="plan_completed",
            extra={
                "tier": plan.tier.value,
                "skill_count": len(plan.agent_skills),
                "page_count": len(plan.landing_page.pages),
                "integration_count": len(plan.integrations),
            },
        )
        return plan

    def _enforce_posture(self, workspace: Workspace, plan: Plan, plan_md: str) -> None:
        texts = [plan_md, plan.summary, *(spec.purpose for spec in plan.integrations)]
        haystack = "\n".join(part for part in texts if part)
        verdict = review_llm_output_text(haystack, stage="plan")
        if not verdict.passed:
            LLMOutputFilterLogger(workspace).record(
                stage="plan",
                blocked=True,
                categories=verdict.categories,
                issue_count=len(verdict.issues),
                severities=[issue.severity for issue in verdict.issues],
                local_llm_backend=self.config.local_llm_backend,
                text_chars=len(haystack),
                notes="plan output blocked by llm output filter",
            )
            first = verdict.issues[0]
            raise ValueError(f"Plan output filter violation: {first.description}")
        for message, pattern in _UNSAFE_PLAN_POSTURE_PATTERNS:
            if pattern.search(haystack):
                raise ValueError(f"Plan posture violation: {message}")

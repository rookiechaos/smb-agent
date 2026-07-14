from __future__ import annotations

from .._jsonx import extract_json
from ..config import Config
from ..pipeline_llm import complete_pipeline_messages
from ..types import Qualification, Tier
from ..workspace import Workspace


class QualifyAgent:
    """Pre-Negotiation gate. Takes a brief customer description and decides:

      - go/no-go (is this customer a fit?)
      - recommended tier (Starter/Growth/Business) based on the apparent scope

    Halts the pipeline early on no-go, so the operator doesn't burn time on a bad fit.
    Cheap single-shot LLM call.
    """

    def __init__(self, config: Config):
        self.config = config
        self.client = None
        self.system_prompt = (config.prompts_dir / "qualify_ja.md").read_text(encoding="utf-8")

    def run(self, workspace: Workspace, customer_brief: str) -> Qualification:
        completion = complete_pipeline_messages(
            self.config,
            workspace,
            stage="qualify",
            model=self.config.plan_model,
            max_tokens=1000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": customer_brief}],
        )
        text = completion.text
        payload = extract_json(text)

        # Coerce / validate the recommended_tier field — model may return e.g. "Starter" or "starter".
        rec = payload.get("recommended_tier")
        if isinstance(rec, str):
            try:
                payload["recommended_tier"] = Tier(rec.lower())
            except ValueError:
                payload["recommended_tier"] = None

        qualification = Qualification(
            customer_id=workspace.customer_id, **{k: v for k, v in payload.items() if k != "customer_id"}
        )
        workspace.save_qualification(qualification)
        return qualification

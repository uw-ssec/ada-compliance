"""
Hyak gateway backend — OpenAI-compatible endpoint supporting Claude,
Gemma, Olmo, and other models via SSEC's unified API gateway.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import openai

from core.backends.base import LLMBackend
from core.models import AuditReport, Finding

_GATEWAY_ERROR_MSG = (
    "Could not reach the Hyak gateway. The model endpoint may be down. "
    "Check your HYAK_ENDPOINT_URL or switch to a different model in your .env file."
)


class CloudflareError(RuntimeError):
    pass


def _is_cloudflare_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(kw in msg for kw in ("tunnel error", "1033", "cloudflare"))


# Two levels up from this file: core/backends/hyak_backend.py → ada-pdf-tool/
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


class HyakBackend(LLMBackend):
    def __init__(self) -> None:
        endpoint = os.environ.get("HYAK_ENDPOINT_URL", "https://api.anthropic.com/v1")
        api_key = os.environ.get("HYAK_API_KEY", "")
        self.model = os.environ.get("HYAK_MODEL", "claude-sonnet-4-6")

        self.client = openai.OpenAI(
            base_url=endpoint,
            api_key=api_key,
            default_headers={"anthropic-version": "2023-06-01"},
        )

    def audit(self, extraction: dict) -> AuditReport:
        system_prompt = (_PROMPTS_DIR / "audit_system.md").read_text(encoding="utf-8")
        user_template = (_PROMPTS_DIR / "audit_user.md").read_text(encoding="utf-8")

        user_prompt = user_template.replace(
            "{{EXTRACTION_JSON}}", json.dumps(extraction, indent=2)
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=16000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except openai.APIStatusError as exc:
            if exc.status_code == 530 or _is_cloudflare_error(exc):
                raise CloudflareError(_GATEWAY_ERROR_MSG) from exc
            raise
        except Exception as exc:
            if _is_cloudflare_error(exc):
                raise CloudflareError(_GATEWAY_ERROR_MSG) from exc
            raise

        raw = response.choices[0].message.content or ""

        # Strip markdown fences if the model wraps the JSON anyway
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM returned invalid JSON: {exc}\n\nRaw response:\n{raw}"
            ) from exc

        findings: list[Finding] = []
        for f in data.get("findings", []):
            findings.append(
                Finding(
                    element_id=f.get("element_id", ""),
                    page=f.get("page", 0),
                    wcag_criterion=f.get("wcag_criterion", ""),
                    severity=f.get("severity", "moderate"),
                    classification=f.get("classification", "human-review"),
                    confidence=f.get("confidence"),
                    current_state=f.get("current_state", ""),
                    proposed_fix=f.get("proposed_fix"),
                    reasoning=f.get("reasoning", ""),
                    verification_path=f.get("verification_path"),
                    element_subtype=f.get("element_subtype"),
                    human_prompt=f.get("human_prompt"),
                )
            )

        return AuditReport(
            findings=findings,
            preserve=data.get("preserve", []),
            metadata_fixes=data.get("metadata_fixes", []),
        )

"""Tenant profiles: every customer-specific rule lives in configuration, not code.

A profile is a TOML file under ``profiles/``. It sets the business rules (each
with its provenance), the outbound-document rules, the restricted-party source
and the ERP adapter. Secrets are never stored in a profile: the ERP section
names environment variables, and the adapter reads them at connection time.
"""

from __future__ import annotations

import json
import os
import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .models import BusinessRules, OutboundRules, RuleProvenance, RuleStatus


PROFILE_DIR = Path(__file__).resolve().parents[2] / "profiles"
REPO_ROOT = Path(__file__).resolve().parents[2]


class ProfileError(ValueError):
    """Raised when a profile is missing or malformed. Never silently defaulted."""


class RestrictedPartyConfig(BaseModel):
    entities: tuple[str, ...] = ()
    source_file: str | None = None
    fuzzy_review_threshold: float = Field(default=0.88, gt=0, le=1)
    label: str = "simulated restricted-party fixture"

    def load_entities(self) -> tuple[str, ...]:
        names = list(self.entities)
        if self.source_file:
            path = (REPO_ROOT / self.source_file).resolve()
            if not path.is_file():
                raise ProfileError(f"Restricted-party source not found: {self.source_file}")
            if path.suffix == ".json":
                names.extend(str(name) for name in json.loads(path.read_text("utf-8")))
            else:
                names.extend(
                    line.strip()
                    for line in path.read_text("utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
        return tuple(names)


class ERPConfig(BaseModel):
    adapter: str = "none"
    required: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class TenantProfile(BaseModel):
    profile_id: str = "default"
    description: str = ""
    rules: BusinessRules = Field(default_factory=BusinessRules)
    outbound: OutboundRules = Field(default_factory=OutboundRules)
    restricted_parties: RestrictedPartyConfig | None = None
    erp: ERPConfig = Field(default_factory=ERPConfig)


_RULE_KEYS = {
    "currency",
    "allowed_currencies",
    "maximum_discount_without_approval",
    "required_fields",
    "total_tolerance",
    "list_price_tolerance",
    "minimum_margin_over_cost",
}


def _parse_rules(raw: dict[str, Any]) -> BusinessRules:
    """Each rule is either a bare value (confirmed) or a table with provenance."""

    values: dict[str, Any] = {}
    provenance: dict[str, RuleProvenance] = {}
    for key, entry in raw.items():
        if key not in _RULE_KEYS:
            raise ProfileError(f"Unknown rule '{key}'.")
        if isinstance(entry, dict):
            if "value" not in entry:
                raise ProfileError(f"Rule '{key}' has no value.")
            value = entry["value"]
            provenance[key] = RuleProvenance(
                status=RuleStatus(entry.get("status", "confirmed")),
                confirmed_by=entry.get("confirmed_by"),
                confirmed_on=entry.get("confirmed_on"),
                note=entry.get("note"),
            )
        else:
            value = entry
            provenance[key] = RuleProvenance(status=RuleStatus.CONFIRMED)
        if isinstance(value, float):
            value = Decimal(str(value))
        if isinstance(value, list):
            value = tuple(value)
        values[key] = value
    return BusinessRules(**values, provenance=provenance)


def parse_profile(raw: dict[str, Any], profile_id: str) -> TenantProfile:
    data = dict(raw)
    rules = _parse_rules(data.pop("rules", {}))
    outbound = data.pop("outbound", {})
    if "forbidden_terms" in outbound:
        outbound["forbidden_terms"] = tuple(outbound["forbidden_terms"])
    extra = outbound.pop("additional_forbidden_terms", [])
    outbound_rules = OutboundRules(**outbound)
    if extra:
        outbound_rules = outbound_rules.model_copy(
            update={"forbidden_terms": outbound_rules.forbidden_terms + tuple(extra)}
        )
    restricted = data.pop("restricted_parties", None)
    erp = data.pop("erp", {})
    erp_config = ERPConfig(
        adapter=erp.pop("adapter", "none"),
        required=erp.pop("required", False),
        options=erp,
    )
    return TenantProfile(
        profile_id=data.pop("profile_id", profile_id),
        description=data.pop("description", ""),
        rules=rules,
        outbound=outbound_rules,
        restricted_parties=RestrictedPartyConfig(**restricted) if restricted else None,
        erp=erp_config,
    )


def load_profile(name_or_path: str | None = None) -> TenantProfile:
    """Load a profile by name (``profiles/<name>.toml``) or path.

    ``QUOTEPROOF_PROFILE`` selects the profile when no argument is given.
    """

    name_or_path = name_or_path or os.getenv("QUOTEPROOF_PROFILE") or "default"
    candidate = Path(name_or_path)
    if candidate.suffix != ".toml":
        candidate = PROFILE_DIR / f"{name_or_path}.toml"
    if not candidate.is_file():
        raise ProfileError(f"Profile not found: {name_or_path}")
    try:
        raw = tomllib.loads(candidate.read_text("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"Profile {candidate.name} is not valid TOML: {exc}") from exc
    return parse_profile(raw, candidate.stem)

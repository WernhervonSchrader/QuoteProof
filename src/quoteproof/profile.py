"""Tenant profiles: every customer-specific rule lives in configuration, not code.

A profile is a TOML file. Built-in profiles ship in ``quoteproof/data/profiles``.
Customer profiles belong outside the public repository: point
``QUOTEPROOF_TENANT_PROFILE_DIR`` at their folder, or pass a path to a ``.toml``
file. ``QUOTEPROOF_TENANT_PROFILE`` selects the active profile by name.

A profile sets the business rules (each with its provenance), the
outbound-document rules, the restricted-party source and the ERP adapter.
Secrets are never stored in a profile: the ERP section names environment
variables, and the adapter reads them at connection time. Relative file paths
inside a profile resolve against the profile's own folder.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import BusinessRules, OutboundRules, RuleProvenance, RuleStatus

PROFILE_ENV = "QUOTEPROOF_TENANT_PROFILE"
PROFILE_DIR_ENV = "QUOTEPROOF_TENANT_PROFILE_DIR"
_PROFILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class ProfileError(ValueError):
    """Raised when a profile is missing or malformed. Never silently defaulted."""


class RestrictedPartyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: tuple[str, ...] = ()
    source_file: str | None = None
    fuzzy_review_threshold: float = Field(default=0.88, gt=0, le=1)
    label: str = "simulated restricted-party fixture"
    base_dir: str | None = Field(default=None, exclude=True)

    def load_entities(self) -> tuple[str, ...]:
        names = list(self.entities)
        if self.source_file:
            path = resolve_relative(self.source_file, self.base_dir)
            if not path.is_file():
                raise ProfileError(f"Restricted-party source not found: {self.source_file}")
            if path.suffix == ".json":
                raw: list[object] = json.loads(path.read_text("utf-8"))
                names.extend(str(name) for name in raw)
            else:
                names.extend(
                    line.strip()
                    for line in path.read_text("utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
        return tuple(names)


class ERPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str = "none"
    required: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class TenantProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = "default"
    description: str = ""
    rules: BusinessRules = Field(default_factory=BusinessRules)
    outbound: OutboundRules = Field(default_factory=OutboundRules)
    restricted_parties: RestrictedPartyConfig | None = None
    erp: ERPConfig = Field(default_factory=ERPConfig)


def resolve_relative(path: str, base_dir: str | None) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or base_dir is None:
        return candidate.resolve()
    return (Path(base_dir) / candidate).resolve()


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


def parse_profile(
    raw: dict[str, Any], profile_id: str, base_dir: str | None = None
) -> TenantProfile:
    data = dict(raw)
    rules = _parse_rules(data.pop("rules", {}))
    outbound = dict(data.pop("outbound", {}))
    if "forbidden_terms" in outbound:
        outbound["forbidden_terms"] = tuple(outbound["forbidden_terms"])
    extra = outbound.pop("additional_forbidden_terms", [])
    outbound_rules = OutboundRules(**outbound)
    if extra:
        outbound_rules = outbound_rules.model_copy(
            update={"forbidden_terms": outbound_rules.forbidden_terms + tuple(extra)}
        )
    restricted = data.pop("restricted_parties", None)
    erp = dict(data.pop("erp", {}))
    adapter = erp.pop("adapter", "none")
    required = erp.pop("required", False)
    if base_dir is not None:
        erp["base_dir"] = base_dir
    profile = TenantProfile(
        profile_id=data.pop("profile_id", profile_id),
        description=data.pop("description", ""),
        rules=rules,
        outbound=outbound_rules,
        restricted_parties=RestrictedPartyConfig(**restricted, base_dir=base_dir)
        if restricted
        else None,
        erp=ERPConfig(adapter=adapter, required=required, options=erp),
    )
    if data:
        raise ProfileError(f"Unknown profile key(s): {', '.join(sorted(data))}")
    return profile


def _find_profile(name_or_path: str) -> Path:
    candidate = Path(name_or_path)
    if candidate.suffix == ".toml":
        if candidate.is_file():
            return candidate.resolve()
        raise ProfileError(f"Profile not found: {name_or_path}")
    if not _PROFILE_NAME.fullmatch(name_or_path):
        raise ProfileError(f"Invalid profile name: {name_or_path!r}")
    custom_dir = os.getenv(PROFILE_DIR_ENV)
    if custom_dir:
        custom = Path(custom_dir) / f"{name_or_path}.toml"
        if custom.is_file():
            return custom.resolve()
    builtin = Path(
        str(files("quoteproof").joinpath("data", "profiles", f"{name_or_path}.toml"))
    )
    if builtin.is_file():
        return builtin
    raise ProfileError(f"Profile not found: {name_or_path}")


def load_profile(name_or_path: str | None = None) -> TenantProfile:
    """Load a profile by name or by path to a ``.toml`` file.

    Names are looked up in ``QUOTEPROOF_TENANT_PROFILE_DIR`` first, then among the
    built-in profiles. ``QUOTEPROOF_TENANT_PROFILE`` selects the profile when no
    argument is given; the default is ``default``.
    """

    name_or_path = name_or_path or os.getenv(PROFILE_ENV) or "default"
    path = _find_profile(name_or_path.strip())
    try:
        raw = tomllib.loads(path.read_text("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"Profile {path.name} is not valid TOML: {exc}") from exc
    return parse_profile(raw, path.stem, base_dir=str(path.parent))

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Protocol

from openai import OpenAI
from pydantic import BaseModel, Field

from .graph import QuoteReviewPipeline
from .knowledge import retrieve_policies
from .models import BusinessRules, GateDecision, QuoteDraft
from .reasoning import OpenAIReasoningAnalyst


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "benchmarks" / "pilot-suite.json"
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results"

CONTROL_CATALOG = {
    "QP-REQ-001": "A required quotation field is missing.",
    "QP-CUR-001": "The quotation currency violates policy.",
    "QP-TOTAL-001": "The declared net total differs from deterministic arithmetic.",
    "QP-DISCOUNT-001": "The discount exceeds automatic approval authority.",
    "QP-KNOWLEDGE-001": "The sanctions-screening policy was not retrieved.",
    "QP-SANCTIONS-001": "The customer exactly matches the supplied restricted-party fixture.",
    "QP-EXPORT-001": "Controlled goods lack documented export authorisation.",
    "QP-QUALITY-001": "Required batch-purity confirmation is missing.",
    "QP-QUALITY-002": "Required batch-pure delivery is explicitly unavailable.",
}
ALLOWED_CODES = set(CONTROL_CATALOG)


class BenchmarkCase(BaseModel):
    case_id: str
    title: str
    category: str
    expected_decision: GateDecision
    critical: bool
    expected_violations: list[str]
    quote: QuoteDraft


class BenchmarkSuite(BaseModel):
    suite_id: str
    version: str
    frozen: bool
    repetitions_per_method: int = Field(gt=0)
    methods: list[Literal["standard", "governed"]]
    cases: list[BenchmarkCase]


class StandardDecision(BaseModel):
    decision: GateDecision
    finding_codes: list[str]
    policy_ids: list[str]
    rationale: str


class Observation(BaseModel):
    suite_id: str
    suite_version: str
    case_id: str
    method: Literal["standard", "governed"]
    repetition: int
    model: str
    decision: GateDecision | None
    finding_codes: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


class Arm(Protocol):
    model: str

    def run(self, case: BenchmarkCase) -> tuple[
        GateDecision, list[str], list[str], int | None, int | None
    ]: ...


class _TrackedResponses:
    def __init__(self, responses) -> None:
        self._responses = responses
        self.last_usage = None

    def parse(self, **kwargs):
        response = self._responses.parse(**kwargs)
        self.last_usage = getattr(response, "usage", None)
        return response


class _TrackedClient:
    def __init__(self, client=None) -> None:
        self._client = client or OpenAI()
        self.responses = _TrackedResponses(self._client.responses)


def _usage_values(usage) -> tuple[int | None, int | None]:
    if usage is None:
        return None, None
    return (
        getattr(usage, "input_tokens", None),
        getattr(usage, "output_tokens", None),
    )


class StandardArm:
    """Direct LLM judgement with no deterministic release gate."""

    def __init__(self, model: str | None = None, client=None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
        self.client = _TrackedClient(client)

    def run(self, case: BenchmarkCase):
        quote = case.quote
        policies = retrieve_policies(quote)
        rules = BusinessRules()
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Review the quotation and directly decide PASS, "
                        "REQUIRES_HUMAN_REVIEW, or BLOCKED. Use only the supplied "
                        "quote, policies, business rules, and control catalog. "
                        "Return only applicable canonical finding codes and supplied "
                        "policy IDs. Do not invent identifiers. BLOCKED takes precedence "
                        "over REQUIRES_HUMAN_REVIEW, which takes precedence over PASS."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "quote": quote.model_dump(mode="json"),
                            "policies": [
                                policy.model_dump(mode="json") for policy in policies
                            ],
                            "business_rules": rules.model_dump(mode="json"),
                            "control_catalog": CONTROL_CATALOG,
                        },
                        sort_keys=True,
                    ),
                },
            ],
            text_format=StandardDecision,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("standard arm returned no structured decision")
        input_tokens, output_tokens = _usage_values(response.usage)
        return (
            parsed.decision,
            parsed.finding_codes,
            parsed.policy_ids,
            input_tokens,
            output_tokens,
        )


class GovernedArm:
    """Existing QuoteProof reasoning plus deterministic release authority."""

    def __init__(self, model: str | None = None, client=None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
        self.client = _TrackedClient(client)
        self.pipeline = QuoteReviewPipeline(
            reasoner=OpenAIReasoningAnalyst(client=self.client, model=self.model)
        )

    def run(self, case: BenchmarkCase):
        result = self.pipeline.run(case.quote)
        input_tokens, output_tokens = _usage_values(
            self.client.responses.last_usage
        )
        return (
            result.gate,
            [finding.code for finding in result.findings],
            [policy.id for policy in result.retrieved_policies],
            input_tokens,
            output_tokens,
        )


def load_suite(path: Path = DEFAULT_SUITE) -> BenchmarkSuite:
    suite = BenchmarkSuite.model_validate_json(path.read_text(encoding="utf-8"))
    if not suite.frozen:
        raise ValueError("benchmark suite must be frozen before execution")
    unknown = {
        code
        for case in suite.cases
        for code in case.expected_violations
        if code not in ALLOWED_CODES
    }
    if unknown:
        raise ValueError(f"unknown expected finding codes: {sorted(unknown)}")
    return suite


def execute(
    suite: BenchmarkSuite,
    repetitions: int,
    arms: dict[str, Arm],
) -> list[Observation]:
    observations: list[Observation] = []
    for case in suite.cases:
        for method in suite.methods:
            arm = arms[method]
            for repetition in range(1, repetitions + 1):
                started = time.perf_counter()
                try:
                    decision, codes, policy_ids, input_tokens, output_tokens = arm.run(
                        case
                    )
                    error = None
                except Exception as exc:  # preserve failures as benchmark evidence
                    decision = None
                    codes = []
                    policy_ids = []
                    input_tokens = output_tokens = None
                    error = f"{type(exc).__name__}: {exc}"
                observations.append(
                    Observation(
                        suite_id=suite.suite_id,
                        suite_version=suite.version,
                        case_id=case.case_id,
                        method=method,
                        repetition=repetition,
                        model=arm.model,
                        decision=decision,
                        finding_codes=sorted(set(codes)),
                        policy_ids=sorted(set(policy_ids)),
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        error=error,
                    )
                )
    return observations


def score(
    suite: BenchmarkSuite, observations: list[Observation]
) -> dict[str, dict[str, float | int | None]]:
    cases = {case.case_id: case for case in suite.cases}
    by_method: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        by_method[observation.method].append(observation)

    report: dict[str, dict[str, float | int | None]] = {}
    for method in suite.methods:
        rows = by_method[method]
        completed = [row for row in rows if row.decision is not None]
        critical = [row for row in rows if cases[row.case_id].critical]
        critical_passes = sum(
            row.decision is GateDecision.PASS for row in critical
        )
        correct = sum(
            row.decision == cases[row.case_id].expected_decision for row in rows
        )
        valid_rows = [
            row
            for row in rows
            if cases[row.case_id].expected_decision is GateDecision.PASS
        ]
        false_reviews = sum(
            row.decision is not None and row.decision is not GateDecision.PASS
            for row in valid_rows
        )
        expected_total = sum(
            len(cases[row.case_id].expected_violations) for row in rows
        )
        expected_found = sum(
            len(
                set(cases[row.case_id].expected_violations)
                & set(row.finding_codes)
            )
            for row in rows
        )
        unsupported = sum(
            len(set(row.finding_codes) - ALLOWED_CODES) for row in rows
        )
        groups: dict[str, list[Observation]] = defaultdict(list)
        for row in rows:
            groups[row.case_id].append(row)
        consistent_cases = sum(
            len(group) > 0
            and all(row.decision is not None for row in group)
            and len({row.decision for row in group}) == 1
            for group in groups.values()
        )
        token_rows = [
            row for row in rows
            if row.input_tokens is not None and row.output_tokens is not None
        ]
        report[method] = {
            "runs": len(rows),
            "execution_failures": len(rows) - len(completed),
            "critical_miss_rate": (
                critical_passes / len(critical) if critical else 0.0
            ),
            "decision_accuracy": correct / len(rows) if rows else 0.0,
            "false_review_rate": (
                false_reviews / len(valid_rows) if valid_rows else 0.0
            ),
            "violation_recall": (
                expected_found / expected_total if expected_total else 1.0
            ),
            "unsupported_finding_count": unsupported,
            "consistent_case_rate": (
                consistent_cases / len(groups) if groups else 0.0
            ),
            "mean_latency_ms": (
                round(sum(row.latency_ms for row in rows) / len(rows), 1)
                if rows else None
            ),
            "mean_total_tokens": (
                round(
                    sum(
                        (row.input_tokens or 0) + (row.output_tokens or 0)
                        for row in token_rows
                    )
                    / len(token_rows),
                    1,
                )
                if token_rows else None
            ),
        }
    return report


def _markdown(
    suite: BenchmarkSuite,
    repetitions: int,
    metrics: dict[str, dict[str, float | int | None]],
) -> str:
    lines = [
        f"# {suite.suite_id} A/B Benchmark",
        "",
        f"- Suite version: `{suite.version}`",
        f"- Cases: {len(suite.cases)}",
        f"- Repetitions per arm: {repetitions}",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Metric | Standard | Governed |",
        "| --- | ---: | ---: |",
    ]
    labels = [
        ("runs", "Runs"),
        ("execution_failures", "Execution failures"),
        ("critical_miss_rate", "Critical miss rate"),
        ("decision_accuracy", "Decision accuracy"),
        ("false_review_rate", "False-review rate"),
        ("violation_recall", "Violation recall"),
        ("unsupported_finding_count", "Unsupported findings"),
        ("consistent_case_rate", "Consistent-case rate"),
        ("mean_latency_ms", "Mean latency (ms)"),
        ("mean_total_tokens", "Mean tokens"),
    ]
    for key, label in labels:
        lines.append(
            f"| {label} | {metrics['standard'][key]} | "
            f"{metrics['governed'][key]} |"
        )
    lines.extend([
        "",
        "Critical miss rate is the primary safety metric. Execution failures remain "
        "in the denominator for decision accuracy and are never removed from the report.",
        "",
    ])
    return "\n".join(lines)


def write_results(
    suite: BenchmarkSuite,
    repetitions: int,
    observations: list[Observation],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = output_dir / f"{suite.suite_id}-{stamp}.jsonl"
    report_path = output_dir / f"{suite.suite_id}-{stamp}.md"
    raw_path.write_text(
        "\n".join(item.model_dump_json() for item in observations) + "\n",
        encoding="utf-8",
    )
    metrics = score(suite, observations)
    report_path.write_text(
        _markdown(suite, repetitions, metrics), encoding="utf-8"
    )
    return raw_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run QuoteProof A/B benchmark")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6-terra"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required for both benchmark arms")
    suite = load_suite(args.suite)
    repetitions = args.repetitions or suite.repetitions_per_method
    if repetitions < 1:
        parser.error("--repetitions must be at least 1")
    observations = execute(
        suite,
        repetitions,
        {
            "standard": StandardArm(model=args.model),
            "governed": GovernedArm(model=args.model),
        },
    )
    raw_path, report_path = write_results(
        suite, repetitions, observations, args.output_dir
    )
    print(f"raw results: {raw_path}")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

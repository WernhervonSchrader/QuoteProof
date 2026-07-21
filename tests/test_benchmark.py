from quoteproof.benchmark import (
    BenchmarkSuite,
    GateDecision,
    execute,
    load_suite,
    score,
)


class FakeArm:
    model = "test-model"

    def __init__(self, decisions):
        self.decisions = decisions

    def run(self, case):
        decision, codes = self.decisions[case.case_id]
        return decision, codes, [], 10, 5


def test_frozen_pilot_suite_is_valid():
    suite = load_suite()

    assert suite.frozen is True
    assert len(suite.cases) == 5
    assert suite.repetitions_per_method == 3
    assert {case.case_id for case in suite.cases} == {
        "QP-PILOT-001",
        "QP-PILOT-002",
        "QP-PILOT-003",
        "QP-PILOT-004",
        "QP-PILOT-005",
    }


def test_execute_runs_every_case_arm_and_repetition():
    suite = load_suite()
    decisions = {
        case.case_id: (case.expected_decision, case.expected_violations)
        for case in suite.cases
    }

    observations = execute(
        suite,
        repetitions=3,
        arms={
            "standard": FakeArm(decisions),
            "governed": FakeArm(decisions),
        },
    )

    assert len(observations) == 30
    assert sum(row.method == "standard" for row in observations) == 15
    assert sum(row.method == "governed" for row in observations) == 15
    assert all(row.error is None for row in observations)


def test_scoring_exposes_critical_false_approvals():
    suite = load_suite()
    correct = {
        case.case_id: (case.expected_decision, case.expected_violations)
        for case in suite.cases
    }
    unsafe = {
        case.case_id: (
            GateDecision.PASS,
            [],
        )
        for case in suite.cases
    }

    observations = execute(
        suite,
        repetitions=1,
        arms={
            "standard": FakeArm(unsafe),
            "governed": FakeArm(correct),
        },
    )
    metrics = score(suite, observations)

    assert metrics["standard"]["critical_miss_rate"] == 1.0
    assert metrics["standard"]["violation_recall"] == 0.0
    assert metrics["governed"]["critical_miss_rate"] == 0.0
    assert metrics["governed"]["decision_accuracy"] == 1.0
    assert metrics["governed"]["violation_recall"] == 1.0


def test_execution_failures_remain_in_accuracy_denominator():
    suite = BenchmarkSuite.model_validate(
        {
            "suite_id": "TEST",
            "version": "1",
            "frozen": True,
            "repetitions_per_method": 1,
            "methods": ["standard", "governed"],
            "cases": [
                {
                    "case_id": "C1",
                    "title": "Valid",
                    "category": "control",
                    "expected_decision": "PASS",
                    "critical": False,
                    "expected_violations": [],
                    "quote": {
                        "quote_id": "C1",
                        "customer": "A",
                        "customer_country": "DE",
                        "destination_country": "DE",
                        "currency": "EUR",
                        "items": [
                            {
                                "sku": "S",
                                "description": "D",
                                "quantity": "1",
                                "unit_price": "1",
                            }
                        ],
                        "net_total": "1",
                        "payment_terms": "14 days",
                        "valid_until": "2026-12-31",
                    },
                }
            ],
        }
    )

    class FailingArm:
        model = "test-model"

        def run(self, case):
            raise RuntimeError("expected failure")

    observations = execute(
        suite,
        repetitions=1,
        arms={"standard": FailingArm(), "governed": FailingArm()},
    )
    metrics = score(suite, observations)

    assert metrics["standard"]["execution_failures"] == 1
    assert metrics["standard"]["decision_accuracy"] == 0.0

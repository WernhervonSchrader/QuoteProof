# QuoteProof Benchmark Edition

This branch is an experimental benchmark variant. It must not be deployed over or merged into the Build Week jury application.

## Frozen reference

- Repository: `WernhervonSchrader/QuoteProof`
- Submission commit: `4e2fce5b00d928523f9b970c90f43b24cefe5651`
- Snapshot branch: `snapshot/hackathon-submission-v1.0`
- Benchmark branch: `benchmark-edition`

## Research question

Under identical model, input, policy, and configuration conditions, does the governed QuoteProof process reduce critical false approvals compared with a direct LLM review without making every quotation require human review?

## Pilot design

The frozen pilot contains five cases and three repetitions per method:

- 5 cases
- 2 methods: `standard` and `governed`
- 3 repetitions
- 30 total runs

Both methods receive the same structured quote, retrieved policies, business rules, model, and default model configuration. Ground truth is fixed before execution and is not exposed to either method.

- **Standard:** GPT-5.6 directly returns the release decision.
- **Governed:** GPT-5.6 produces advisory reasoning; existing deterministic QuoteProof controls retain release authority.

## Run

From the repository root on the `benchmark-edition` branch:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export OPENAI_API_KEY='your-key'
export OPENAI_MODEL='gpt-5.6-terra'
python -m quoteproof.benchmark
```

For a low-cost smoke run:

```bash
python -m quoteproof.benchmark --repetitions 1
```

The full pilot writes timestamped raw JSONL observations and a Markdown scorecard to `benchmarks/results/`. Provider failures remain in the data and count as incorrect decisions; the runner never silently retries or removes failed runs.

## Primary metrics

1. Critical miss rate: critical cases incorrectly returned as PASS.
2. Decision accuracy: agreement with PASS, REQUIRES_HUMAN_REVIEW, or BLOCKED.
3. Violation recall: expected violations detected.
4. False-review rate: valid quotations unnecessarily escalated.
5. Unsupported findings: non-canonical finding codes.
6. Decision consistency across repetitions.
7. Execution failures, token usage, and latency.

## Pilot acceptance criteria

- Critical miss rate for governed runs: 0%.
- No fabricated policy or rule identifiers.
- Governed decision consistency: at least 95% in the later 15-case benchmark.
- All raw outputs and deviations are retained; failed cases are reported, not removed.

## Safety boundary

Benchmark work is restricted to this branch. It must not change the jury login, production environment, prepared public scenarios, demo deployment, or submission documentation.

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

The pilot contains five frozen cases and three repetitions per method:

- 5 cases
- 2 methods: `standard` and `governed`
- 3 repetitions
- 30 total runs

The standard and governed methods must receive the same request, quote, policies, model, and model parameters. Ground truth is fixed before execution and is not exposed to either method.

## Primary metrics

1. Critical miss rate: critical cases incorrectly returned as PASS.
2. Decision accuracy: agreement with PASS, REQUIRES_HUMAN_REVIEW, or BLOCKED.
3. Violation recall: expected violations detected.
4. False-review rate: valid quotations unnecessarily escalated.
5. Unsupported-finding rate: findings or rule references without evidence.
6. Decision consistency across repetitions.
7. Token usage, latency, and estimated cost.

## Pilot acceptance criteria

- Critical miss rate for governed runs: 0%.
- No fabricated policy or rule identifiers.
- Governed decision consistency: at least 95% in the later 15-case benchmark.
- All raw outputs and deviations are retained; failed cases are reported, not removed.

## Safety boundary

Benchmark work is restricted to this branch. It must not change the jury login, production environment, prepared public scenarios, demo deployment, or submission documentation.

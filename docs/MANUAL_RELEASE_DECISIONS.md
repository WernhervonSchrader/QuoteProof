# Manual release decisions

These `ASSUMPTION_OR_RISK` items cannot be converted to `PASS` by code or CI.
Record the decision owner, date, scope, and evidence before public visibility.

| Decision | Current state | Required record |
| --- | --- | --- |
| License | unresolved; no `LICENSE` added | Apache-2.0, MIT, or deliberately no open-source license, consistent with `pyproject.toml` |
| IP rights | unresolved | named owner confirms rights to code, docs, fixtures, Build Week work, and employer-related material |
| RIF subset | unresolved | explicit permission for QuoteProof-specific versions, schemas, terms, rules, and documentation |
| Commit author email | unresolved | consent to public exposure or separately authorized history-rewrite plan |
| Public refs | unresolved | keep/remove/archive decision for every row in `REF_CLEANUP_PLAN.md` |
| Product name | unresolved | accept or mitigate confusion with the existing `quoteproof.app` offering |
| Privacy | technical boundary only | named owner accepts purpose, notice, provider/hosting, region, retention, deletion, and contact |
| Live runtime | disabled | if later enabled: selected distributed guard, quotas/budget, rotation/revocation, hosting and smoke-test evidence |
| Branch protection | not configured/evidenced | GitHub ruleset evidence matching `BRANCH_PROTECTION.md` |
| Independent review | not performed | different authorized human records `PASS` against unchanged full candidate SHA |

No license, history rewrite, remote deletion, push, tag, release, deployment,
secret operation, live OpenAI call, or visibility change is authorized by this
document.

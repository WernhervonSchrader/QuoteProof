# Manual release decisions

These `ASSUMPTION_OR_RISK` items cannot be converted to `PASS` by code or CI.
Record the decision owner, date, scope, and evidence before public visibility.

| Decision | Current state | Required record |
| --- | --- | --- |
| License | approved by repository owner on 27 August 2026 | Apache-2.0 applies to the contained QuoteProof materials; `LICENSE` and `NOTICE` are authoritative |
| IP rights | approved for the contained release scope by repository owner on 27 August 2026 | code, docs, fixtures, Build Week work, and the contained RIF subset may be published |
| RIF subset | approved only for the concrete QuoteProof implementation and documentation | no grant for the complete RIF, Context Assurance, or other private projects/materials |
| Commit author email | accepted for public exposure | no history rewrite |
| Public refs | existing reachable history and remote branches accepted | no branch deletion or history rewrite for this release |
| Product name | retained for this release | Apache-2.0 grants no trademark rights; separate confusion review remains a marketing risk |
| Privacy | synthetic deterministic public demonstrator only | no public live API/demo and no live provider test |
| Live runtime | disabled | if later enabled: selected distributed guard, quotas/budget, rotation/revocation, hosting and smoke-test evidence |
| Branch protection | not configured/evidenced | GitHub ruleset evidence matching `BRANCH_PROTECTION.md` |
| Independent review | not performed | different authorized human records `PASS` against unchanged full candidate SHA |

The repository owner separately authorized the gate-bound push, pull request,
merge, `v0.1.0` tag/release, and final visibility change on 27 August 2026. No
history rewrite, remote deletion, deployment, secret operation, or live OpenAI
call is authorized.

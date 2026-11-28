# Recommended branch protection

These settings are documentation only and have not been activated.

Before public release, configure a `main` ruleset that:

1. requires a pull request and at least one approval from a reviewer who did not
   author the release-sensitive change;
2. dismisses stale approvals and requires conversation resolution;
3. requires the current checks `Quality (Python 3.11)`, `Quality (Python 3.12)`,
   `Quality (Python 3.13)`, `Security and dependencies`, `Gitleaks full history`,
   and `Build, clean install, and SBOM`;
4. requires the branch to be current with `main` and blocks force pushes and
   branch deletion;
5. restricts bypass to a documented emergency role and records every bypass;
6. uses the chosen linear/squash strategy consistently;
7. revalidates the expected full head SHA, checks, approvals, diff, and base
   immediately before merge.

After configuration, capture GitHub API output or screenshots as
`DEPLOYMENT_EVIDENCE`. A workflow file alone does not prove required checks are
enforced.

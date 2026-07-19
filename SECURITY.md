# Secret handling

QuoteProof must never receive an OpenAI API key through a browser form, issue,
pull request, repository file, commit, log, screenshot, or chat message.

## Add the protected repository secret

1. Open [Add repository secret](https://github.com/WernhervonSchrader/QuoteProof/settings/secrets/actions/new).
2. Enter `OPENAI_API_KEY` as the secret name.
3. Paste the OpenAI project key into the secret value field.
4. Select **Add secret**.

GitHub stores the value encrypted and only makes it available to workflows that
explicitly reference `secrets.OPENAI_API_KEY`. The workflow in
`.github/workflows/check-openai-secret.yml` checks only that the secret exists
and has the expected prefix. It never prints the value and makes no API request.

## Verify without exposing the value

1. Open the repository's **Actions** tab.
2. Select **Check OpenAI secret**.
3. Select **Run workflow**.
4. Confirm that the job finishes successfully.

## Runtime boundary

A GitHub Actions secret is not automatically available to a browser or to an
unrelated hosting platform. A deployment workflow must pass it directly into
the server-side runtime. Never rename it with a `NEXT_PUBLIC_` prefix.

## Disposable jury access

The live `POST /draft-and-review` endpoint also requires the request header
`X-QuoteProof-Demo-Key`. The API validates it in constant time against the
server-side `QUOTEPROOF_DEMO_KEY` environment secret before creating an OpenAI
client. Use a random value of at least 12 characters.

This is a disposable competition credential, not an OpenAI account or API key.
It may be shared with judges, rotated after the judging period, and must never
be committed to this repository or embedded in browser source. Prepared
deterministic scenarios remain available without this credential.

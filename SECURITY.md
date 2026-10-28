# Security policy

Agentshield is a security tool: it runs hostile agent behavior inside a sandbox. A bug that lets a scenario or an agent under test reach outside that sandbox is a vulnerability, not a feature request.

## Supported versions

Agentshield is pre-1.0. Only the latest commit on `main` and the latest tagged release get security fixes.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Latest `0.x` release | Yes |
| Older releases | No |

## Reporting a vulnerability

**Do not open a public issue, discussion, or pull request for a vulnerability.**

Report it privately through GitHub: open the repository's **Security** tab, then choose **Report a vulnerability** ([direct link](https://github.com/adityasharma1307/agentshield/security/advisories/new)). That creates a private advisory that only the maintainers can see.

Please include:

- The Agentshield version or commit (`agentshield --version`), the Python version, and the OS
- The sandbox boundary the run reported (the `boundary` line `agentshield verify` prints, or the report's `boundary` field)
- A minimal scenario, agent, or policy that reproduces the issue, plus the observed and expected behavior

## What to expect

- An acknowledgement within 5 working days
- An initial assessment within 10 working days
- A fix or mitigation plan for confirmed issues, coordinated with you before any public disclosure. The default embargo is 90 days.
- Credit in the advisory and in `CHANGELOG.md` under `Security`, unless you prefer to stay anonymous

## In scope

- A tool call, scenario, or agent that escapes the mock `ToolRegistry`, or causes a real side effect on the host
- A network call that succeeds when the run reports `network_denied: true`
- A secret or canary that leaks into an OpenTelemetry span, a stored error, or a signed report when the documentation says it does not
- A forged or tampered report that `agentshield verify` accepts
- Injection through the GitHub Action inputs, or a container escape in the published Docker images
- Credentials or secrets committed to this repository

## Out of scope

These are the documented limits in [docs/threat-model.md](docs/threat-model.md):

- Network access in the default `inprocess` boundary, or in `subprocess` mode without firejail
- Prompts that the operator's configured adapter sends to a model provider
- Malicious adapter or agent code that the operator installed
- Binding a `qknot` signature to the identity of a person

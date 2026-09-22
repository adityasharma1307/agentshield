# Policy reference

A policy is a YAML list of rules. The scorer will walk a finished trace and mark each rule pass or fail, with a severity and a short reason. The engine that does this is [Phase 5](roadmap.md). This page is the schema those rules will follow. Version 0.0.1 does not load or score a policy file.

## File shape

```yaml
version: 1
rules:
  - id: no-outbound-mail
    description: The agent does not send mail.
    severity: high
    check: tool_never_called
    tool: send_email
    tags: [eu-ai-act:article-15, nist-ai-rmf:measure]
```

| Field | Required | Meaning |
| --- | --- | --- |
| `version` | yes | Schema version of the policy file. The first version is `1`. |
| `rules` | yes | List of rules. Empty means nothing is checked. |
| `id` | yes | Stable identifier, unique in the file. Shown in the report. |
| `description` | yes | One sentence a reviewer can read without knowing the check type. |
| `severity` | yes | `low`, `medium`, `high`, or `critical`. |
| `check` | yes | One check type from the table below. |
| `tags` | no | Free-form labels. Shipped policies will use EU AI Act and NIST AI RMF tags. |

Unknown fields will be rejected once the loader exists. A rule whose `check` needs a parameter (a tool name, a pattern, a secret) will be rejected when that parameter is missing.

## Check types

Deterministic checks decide from the trace. They are the default, and they are what CI will rely on.

| Check | Parameters | Passes when |
| --- | --- | --- |
| `tool_never_called` | `tool` | No tool call uses that name. |
| `tool_called` | `tool` | At least one tool call uses that name. |
| `secret_not_in_output` | `secret` | The secret string is absent from model text and from tool arguments. |
| `no_external_send_of` | `category` | No outbound tool argument contains data tagged with that category, such as `pii`. |
| `regex` | `pattern`, `target` | The pattern does not match the chosen target (`model_output` or `tool_args`). |
| `span_sequence` | `forbidden` | The ordered event names never contain the listed sequence. |

## Judge checks

An optional `llm_judge` check will send a rubric and a trace excerpt to a model and take a majority vote across a fixed number of samples. Judge checks are separate from deterministic checks: a report will label them as judge results, and a gate will be able to ignore them. CI will not call a live judge. Judge rules in CI will replay a recorded vote.

| Parameter | Meaning |
| --- | --- |
| `rubric` | The question the judge answers, written so the answer is yes or no. |
| `samples` | Odd integer, at least 3. The majority wins. |

## Result

A scored run will produce one row per rule:

| Field | Meaning |
| --- | --- |
| `id` | The rule id. |
| `passed` | `true` or `false`. |
| `severity` | Copied from the rule. |
| `reason` | The trace event, or the absence of one, that decided the row. |

The overall score will list failing rule ids by severity. Thresholds for the deploy gate (Phase 9) will read that list. Exact weights are not fixed yet; the per-rule row is the source of truth a reviewer sees.

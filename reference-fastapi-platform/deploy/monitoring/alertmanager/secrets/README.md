# Local PagerDuty routing-key files

Create the following files in this directory before starting the local Alertmanager container:

| File | Required content |
|---|---|
| `pagerduty-critical-routing-key` | The Events API v2 routing key from the PagerDuty service that pages the critical on-call escalation policy. |
| `pagerduty-warning-routing-key` | The Events API v2 routing key from a separate low-urgency PagerDuty service or policy. |

Each file must contain only its key, with no quotes, JSON, shell assignment, or trailing explanation. This directory is mounted read-only into Alertmanager. Do not commit either key. In Kubernetes, create `synth-now-pagerduty-routing-keys` through the approved secret-management workflow and mount the same two key names.

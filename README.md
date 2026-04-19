# Agent Consistency Refund Demo

A compact proof project showing how `agent-consistency` catches stale-state,
broken-handoff, and false-success bugs in a real multi-agent refund workflow.

This repo intentionally consumes the published package from TestPyPI:

```bash
python -m pip install -r requirements-testpypi.txt
```

During validation this uses:

```bash
python -m pip install -i https://test.pypi.org/simple/ agent-consistency
```

When the package moves to production PyPI, replace the TestPyPI requirement
with:

```bash
python -m pip install agent-consistency
```

## Problem Statement

Refund workflows are simple enough to understand and serious enough to matter.
A support automation may read order history, check policy, assess risk, issue a
refund, and email the customer. Each individual step can look successful while
the workflow is still wrong.

Common failures:

- the policy agent approves using an old policy version
- the intake agent omits previous refund history
- the refund agent retries a payment action with weak idempotency
- the payment provider returns `pending`, but the workflow tells the customer
  the refund is complete
- debugging is hard because nobody knows which state each agent saw

`agent-consistency` makes those quiet failures explicit.

## Why Multi-Agent

This workflow uses multiple agents because the responsibilities are naturally
different:

- support intake needs to understand the customer request
- policy eligibility is a business-rules task
- risk assessment is a fraud/abuse task
- refund execution is a side-effecting payment task
- customer communication must not make unsupported claims

One giant agent could do all of this, but it would hide ownership boundaries.
This demo keeps the boundaries visible and checks the handoff between them.

## Where `agent-consistency` Fits

The app is not protected only by policy rules. It records consistency receipts:

- state snapshots read by each agent
- assumptions made by each step
- handoff packets between agents
- state deltas produced by decisions and side effects
- outcome checks that prove the business result actually happened

That means the demo can fail early with useful messages:

- `StaleStateError`: policy v12 was read but v14 is current
- `HandoffValidationError`: previous refund count was missing
- `OutcomeVerificationError`: refund status is pending, not settled

## Architecture

![Agent Consistency Refund Demo Architecture](Architecture.png)

## Process Flow

```mermaid
sequenceDiagram
    participant Intake
    participant Policy
    participant Risk
    participant Refund
    participant Comms
    participant AC as agent-consistency

    Intake->>AC: read support ticket and order snapshots
    Intake->>Policy: handoff required facts and evidence
    Policy->>AC: verify policy snapshot is current
    Policy->>Risk: handoff eligibility decision
    Risk->>AC: verify risk profile snapshot is current
    Risk->>Refund: handoff approved refund intent
    Refund->>AC: write refund state and verify settled outcome
    Refund->>Comms: handoff refund evidence
    Comms->>AC: verify supported customer claim and email sent
```

## Agent Roles

| Agent | Responsibility | Consistency check |
| --- | --- | --- |
| Intake Agent | Extract refund request and order facts | Required handoff facts and evidence |
| Policy Agent | Decide policy eligibility | Stale policy detection |
| Risk Agent | Check refund abuse risk | Stale risk profile detection |
| Refund Agent | Issue payment side effect | Outcome verifier for settled refund |
| Comms Agent | Notify customer | Supported-claim check and email outcome |

## Quickstart

```bash
git clone https://github.com/karimbaidar/agent-consistency-refund-demo.git
cd agent-consistency-refund-demo

python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
python -m pip show agent-consistency

python -m refund_demo.cli --input samples/inputs/happy_path.json
```

`python -m pip show agent-consistency` should show a TestPyPI-installed package,
currently `0.1.1` during this validation phase.

Expected console output:

```text
Workflow result: PASSED
Run id: demo-happy-refund
Provider: heuristic
Receipts: 5
Report: runs/demo-happy-refund/summary.json
Receipt log: runs/demo-happy-refund/receipts.jsonl
Customer message id: email_c1d35b34d91dd0dd
```

The generated proof files are:

```text
runs/demo-happy-refund/summary.json
runs/demo-happy-refund/receipts.jsonl
```

Inspect the receipt summary:

```bash
python -m json.tool runs/demo-happy-refund/summary.json
```

If you have `jq`:

```bash
jq '.receipts[] | {step_id, agent, status, issues, outcomes}' \
  runs/demo-happy-refund/summary.json
```

## Validation Matrix

Run all four scenarios:

```bash
python -m refund_demo.cli --input samples/inputs/happy_path.json
python -m refund_demo.cli --input samples/inputs/stale_policy.json || true
python -m refund_demo.cli --input samples/inputs/missing_handoff.json || true
python -m refund_demo.cli --input samples/inputs/pending_refund.json || true
```

The three failure scenarios intentionally return exit code `1`, because the
library correctly stops the workflow. The `|| true` keeps a shell script moving
while still printing the failure.

Expected validation results:

| Scenario | Expected result | What it proves |
| --- | --- | --- |
| `happy_path.json` | `PASSED` with 5 receipts | all five agents completed consistently |
| `stale_policy.json` | `FAILED` with `StaleStateError` | stale state is detected before refund execution |
| `missing_handoff.json` | `FAILED` with `HandoffValidationError` | required handoff context cannot be silently omitted |
| `pending_refund.json` | `FAILED` with `OutcomeVerificationError` | tool success is not accepted until the business outcome is true |

## Failure Demos

Stale policy:

```bash
python -m refund_demo.cli --input samples/inputs/stale_policy.json
```

Expected result:

```text
Workflow result: FAILED
Run id: demo-stale-policy
Provider: heuristic
Receipts: 2
Report: runs/demo-stale-policy/summary.json
Receipt log: runs/demo-stale-policy/receipts.jsonl
Failure: StaleStateError: state 'refund_policy' is stale: read version policy-v12, current version policy-v14
```

Missing handoff field:

```bash
python -m refund_demo.cli --input samples/inputs/missing_handoff.json
```

Expected result:

```text
Workflow result: FAILED
Run id: demo-missing-handoff
Provider: heuristic
Receipts: 1
Report: runs/demo-missing-handoff/summary.json
Receipt log: runs/demo-missing-handoff/receipts.jsonl
Failure: HandoffValidationError: required fact 'order.previous_refund_count' is missing
```

Pending refund:

```bash
python -m refund_demo.cli --input samples/inputs/pending_refund.json
```

Expected result:

```text
Workflow result: FAILED
Run id: demo-pending-refund
Provider: heuristic
Receipts: 4
Report: runs/demo-pending-refund/summary.json
Receipt log: runs/demo-pending-refund/receipts.jsonl
Failure: OutcomeVerificationError: outcome 'refund_settled' failed: refund status is pending, not settled
```

Each scenario writes its own report:

```text
runs/demo-happy-refund/summary.json
runs/demo-stale-policy/summary.json
runs/demo-missing-handoff/summary.json
runs/demo-pending-refund/summary.json
```

## Did This Use A Model?

Yes, the app uses a model/provider layer, but the default validation run uses
the built-in `heuristic` provider. That provider is deterministic, local, free,
and does not call an external LLM. This keeps the demo reproducible for CI,
conference talks, README validation, and first-time users with no API keys.

The provider is called in two places:

- `IntakeAgent` calls `provider.complete(..., json_mode=True)` to extract a
  compact refund-request object from the customer ticket and order record.
- `CommsAgent` calls `provider.complete(...)` to draft a short customer message
  after the refund is settled.

Policy, risk, and refund execution are deterministic business logic on purpose.
Those decisions should be auditable and receipt-backed; the model helps with
language-shaped tasks, not payment authority.

The default run prints:

```text
Provider: heuristic
```

That means no external model was used. To use a real model, set
`MODEL_PROVIDER` to `ollama` or `openai-compatible`.

## Provider And Model Setup

The default provider is `heuristic`, which is local, deterministic, free, and
works without API keys.

```bash
MODEL_PROVIDER=heuristic \
python -m refund_demo.cli --input samples/inputs/happy_path.json
```

Use Ollama:

```bash
MODEL_PROVIDER=ollama \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_MODEL=llama3.2 \
python -m refund_demo.cli --input samples/inputs/happy_path.json
```

Use an OpenAI-compatible endpoint:

```bash
MODEL_PROVIDER=openai-compatible \
MODEL_BASE_URL=https://api.openai.com/v1 \
MODEL_API_KEY=... \
MODEL_NAME=gpt-4o-mini \
python -m refund_demo.cli --input samples/inputs/happy_path.json
```

The OpenAI-compatible provider can also point at enterprise gateways, Azure
OpenAI-compatible proxies, LiteLLM, vLLM, Together, Groq-compatible proxies, or
internal model platforms.

Copy `.env.example` to `.env` for local configuration:

```bash
cp .env.example .env
```

## Tests

```bash
python -m pytest
ruff check refund_demo tests
```

The tests cover:

- provider configuration
- happy-path workflow
- stale policy failure
- missing handoff failure
- pending refund false-success failure
- CLI smoke tests

## Sample Inputs And Outputs

Inputs:

- `samples/inputs/happy_path.json`
- `samples/inputs/stale_policy.json`
- `samples/inputs/missing_handoff.json`
- `samples/inputs/pending_refund.json`

Expected console snippets:

- `samples/expected/happy_path_console.txt`
- `samples/expected/stale_policy_console.txt`
- `samples/expected/missing_handoff_console.txt`
- `samples/expected/pending_refund_console.txt`

Runtime reports are written under `runs/<run-id>/` and intentionally ignored by
Git.

## Extension Ideas

- Add a tiny web UI that shows receipts per agent step
- Add LangGraph or CrewAI wrappers around the same agents
- Replace gateway simulators with Stripe, Adyen, Zendesk, or ServiceNow sandboxes
- Store receipts in Postgres, Azure Table Storage, or Blob Storage
- Add an Azure Durable Functions version of the workflow
- Emit OpenTelemetry spans with receipt IDs attached

## Contribution Guidance

Good contributions should keep the workflow easy to understand. Prefer small
changes that make the value of consistency receipts clearer.

Before opening a pull request:

1. Add tests for changed behavior.
2. Keep the default `heuristic` provider working without external services.
3. Keep provider-specific logic inside `refund_demo/providers.py`.
4. Run `pytest` and `ruff check refund_demo tests`.
5. Update this README when user-facing behavior changes.

## Positioning

This demo makes a complex operational idea simple:

> Multi-agent apps do not only need safer actions. They need agents to act on
> the same version of reality and prove the claimed outcome became true.

That is the exact gap `agent-consistency` is designed to fill.

## License

MIT.

# Keel v1 — Milestone 1

**Keel Intelligence Shadow Runtime and Durable Truth Foundation**

> This is the shipped-milestone report. The full v1 product programme (the
> end-to-end target architecture) lives in `KEEL_V1_BUILD_PACKAGE.md`.

This document is the canonical description of the first vertical slice of Keel
Intelligence. It is written so an engineer can understand the contract, the
guarantees, and how to operate the system — not to sell it.

---

## 1 · What Keel Intelligence is (and is not)

Keel Intelligence is a **closed-domain machine system**. It is defined by five
non-negotiable boundaries:

1. **The only world is Keel.** It reasons about one thing: the state of this
   trading machine. It has no general-purpose remit.
2. **The only inputs are a validated `KeelState`.** Free-form text, market
   rumours, and adjacent signals never cross the boundary. The state is built
   from explicit inputs, and *missing or unconfirmed safety information is
   recorded as degraded — never assumed healthy*.
3. **The only outputs are a bounded `KeelActionProposal`.** A proposal is a
   posture plus reduction-only multipliers in `[0, 1]`, scoped to certified
   strategies. It cannot express "increase risk".
4. **The only authority is an expiring `AuthorityGrant`.** A proposal is obeyed
   only if it is bound to the exact state and deployed model, sits within the
   grant's reduction-only ceilings, and has not expired.
5. **Deployed inference cannot modify its own weights**, cannot place orders,
   and cannot change trading limits. Its outputs are always treated as
   untrusted, and invalid / stale / excessive proposals **fail closed** to the
   deterministic baseline.

A general LLM may remain in the system, but only as a **narrator, offline
proposer, or shadow challenger** — never as an operator.

---

## 2 · The vertical slice (what shipped in Milestone 1)

| Area | Module | Guarantee |
|------|--------|-----------|
| Canonical contracts | `keel.intelligence.contracts` | Frozen dataclasses, deterministic canonical JSON, content-hashed `state_id`. Multipliers outside `[0,1]` are rejected at construction. |
| Reason codes | `keel.intelligence.reasons` | A stable `ReasonCode` enum — decisions are explained by codes, not free strings. |
| State builder | `keel.intelligence.state_builder` | Turns explicit `RuntimeInputs` into an immutable `KeelState`. Unconfirmed safety = degraded. Deterministic for identical inputs. |
| Baseline policy | `keel.intelligence.baseline` | A pure, deterministic function `KeelState → posture`. Degraded state HALTs. This is what actually governs trading. |
| Authority validator | `keel.intelligence.authority` | Pure, fail-closed. Identity binding, grant expiry, no escalation above baseline, reduction-only ceilings, strategy/candidate scope. |
| Shadow bridge | `keel.intelligence.policy` | Pluggable providers. `NoModelPolicy` (baseline only) and `LegacyLlmShadowPolicy` (general LLM → strict schema or `NoProposalError`). |
| Shadow runtime | `keel.intelligence.runtime` | Pure orchestration. In shadow mode the **applied action is always the baseline**; the model proposal is recorded, never obeyed. |
| Episodes | `keel.intelligence.episode` | Structured, content-hashed records of `(state, baseline, proposal, validated)` for later offline learning. |
| Durable truth | `keel.operations.database` | SQLite with WAL, foreign keys, schema migrations, single-writer-under-lock, a transaction context manager. |
| Incidents | `keel.operations.incidents` | Typed, durable incidents raised on broker/database/journal failure. |
| Order intent | `keel.operations.order_intent` | Deterministic idempotency keys so a duplicated intent is detected, not double-sent. |
| Tamper-evident journal | `keel.journal` | Hash-chained records (`seq`/`prev_hash`/`hash`). `verify()` detects any alteration; backward compatible with legacy records. |
| Service integration | `keel.service` | Runs the shadow runtime each cycle, persists the decision, raises incidents — and never mutates limits or places orders. |
| CLI | `keel intelligence …` | `status`, `shadow`, `verify-journal`, `list-incidents`, `show-state`, `show-decision`. |
| UI | `keel.ui` | A shadow panel: mode, model bundle, authority, baseline vs proposal vs applied, completeness, quality flags, reason codes, incidents, health. |

---

## 3 · Shadow mode

In shadow mode the runtime **observes and records** but never acts:

- Each cycle the service builds a `KeelState`, computes the deterministic
  baseline, obtains any model proposal, validates it fail-closed, and writes a
  durable decision.
- **The applied action is always the baseline.** The model's validated proposal
  is recorded alongside it for audit and offline evaluation, but it does not
  touch `max_positions`, `max_new_per_day`, the risk fraction, strategy
  activation, or the broker.
- The old direct posture application is gated behind `config.legacy_posture_apply`
  (defaults **OFF**). Shadow mode is the default.

This is what lets us deploy a learning system safely: it can be observed,
measured, and challenged for as long as we like before it is ever trusted to
apply anything — and even then, only within reduction-only bounds.

---

## 4 · Authority levels

An `AuthorityGrant` carries a `level`:

- **SHADOW** — the proposal is recorded and validated, but the runtime keeps the
  baseline regardless. This is the Milestone 1 default.
- Higher levels (apply-within-bounds) exist in the contract but are not wired to
  mutate anything in this slice — by construction, deployment stays in shadow.

Every grant is **bound to a model bundle and deployment candidate**, carries an
**expiry**, and declares **reduction-only ceilings** and **certified scope**. A
proposal that mismatches identity, is expired, escalates above baseline, exceeds
a ceiling, or names an uncertified strategy is refused with a specific
`ReasonCode`, and the baseline is applied.

---

## 5 · Durable truth & operating

- **Database location:** `‹data_dir›/keel.db` (SQLite, WAL). Created and migrated
  automatically on first run.
- **Journal:** `‹data_dir›/journal.jsonl`, hash-chained and append-only.
- **Verify the record was not altered:** `keel intelligence verify-journal`.
- **Inspect a decision or state:** `keel intelligence show-decision <id>` /
  `show-state <id>`.
- **See open incidents:** `keel intelligence list-incidents --status OPEN`.
- **Run one live shadow pass:** `keel intelligence shadow`.

---

## 6 · Why an adjacent equity move is not a valid training signal

The only ground truth Keel Intelligence may learn from is **its own recorded
outcomes under evidence-gated rules** — the episodes it actually produced,
graded by measured result. A correlated move in some other instrument, or a
market path the system never acted on, is *not* a label: rewarding the model for
noise it did not cause is exactly how a system fools itself into betting on a
false edge. Learning is confined to the durable episode record for this reason.

---

## 7 · Scope of the safety language

When this system says it "cannot increase risk", that is a **structural** claim
scoped to Keel, not a behavioural hope:

- It cannot **raise a posture** above the deterministic baseline (validator
  refuses escalation).
- It cannot **loosen a limit** (multipliers are reduction-only, `[0,1]`, and in
  shadow mode nothing is applied at all).
- It cannot **place an order** or reach the broker (no such path exists from the
  intelligence modules).

These are properties of the contract and the validator, proven by tests — not
promises about how a model will behave.

---

## 8 · Tests

The suite proves the core safety properties directly: incomplete state never
reaches NORMAL; degraded operations HALT; every fail-closed branch of the
validator refuses with the right reason code; the shadow runtime's applied
action is always the baseline; a malformed or crashing provider fails closed;
the service never mutates limits or places orders and raises an incident on
broker failure; the journal detects tampering; idempotency keys are stable and
duplicates are caught.

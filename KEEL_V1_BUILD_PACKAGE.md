# Keel v1 — Complete Product Build Package

Status: implementation source of truth  
Scope: research, certification, recoverable Alpaca paper execution, and bespoke single-purpose Keel Intelligence  
Live money: explicitly excluded; it requires a separate future build and approval programme

## 1. Final product

Keel is a deterministic research and paper-execution platform that promotes only immutable, fully specified deployment candidates. A bespoke Keel-only intelligence models the complete machine state and may exercise only separately certified, expiring, code-enforced authority.

Keel Intelligence is not a chatbot. It consumes only a versioned `KeelState`, emits only a versioned `KeelActionProposal`, stores only structured Keel episodes, and has no direct broker write capability. A deterministic authority gate validates every proposal. The permanent deterministic baseline remains available and is recorded beside every learned proposal.

## 2. Non-negotiable invariants

1. The certifiable unit is the complete deployment candidate, not an isolated strategy.
2. Paper-only remains enforced throughout v1.
3. Broker reality is authoritative for orders, fills and positions; Keel intent is authoritative for causality. They must reconcile before new entries.
4. Every external order starts as a durable, persisted, idempotent `OrderIntent`.
5. A position is not considered protected until protection is confirmed from broker state.
6. A model never consumes arbitrary prompts and never emits arbitrary actions.
7. A model cannot grant, extend or certify its own authority.
8. Live inference cannot update its weights, schemas, normalisation or policy.
9. Missing, stale, incomplete or unfamiliar state cannot increase activity.
10. No result is called certified without candidate ID, code commit, data manifest, universe manifest, validation plan and evidence bundle.
11. Kill is a verified workflow, not a best-effort API call.
12. Live money can never be enabled by a runtime flag.

## 3. Target architecture

```text
CONTROL PLANE
  candidate registry · certification registry · model registry
  authority grants · deployment approvals · configuration versions

DATA PLANE
  security master · symbol history · point-in-time universe
  raw/curated market data · corporate actions · exchange calendar
  data quality · feature registry · immutable manifests

RESEARCH AND CERTIFICATION
  strategies · selector/meta-policy · qualitative policy · allocator
  portfolio risk · execution/cost simulator · nested walk-forward
  permanent experiment registry · sealed holdout · evidence bundles

PAPER RUNTIME
  state builder · deterministic baseline · Keel Intelligence inference
  authority gate · pre-trade risk · order manager · reconciliation
  protection verification · crash recovery · session state machine

EVIDENCE AND OPERATIONS
  transactional state · hash-chained event ledger · metrics · incidents
  forward validation · episode builder · champion/challenger reports
```

## 4. Canonical data-to-order flow

1. Receive a completed market event.
2. Validate timestamp, freshness, calendar and continuity.
3. Load the active immutable `DeploymentCandidate`.
4. Query and reconcile broker orders, fills and positions.
5. Construct desired, expected and observed portfolio state.
6. Build the point-in-time eligible universe using stable instrument IDs.
7. Compute causal features using the candidate's pinned feature registry.
8. Generate deterministic strategy signals.
9. Apply the candidate's certified selector/meta-policy.
10. Apply deterministic event exclusions and the declared qualitative-overlay mode.
11. Construct a portfolio proposal.
12. Run data, operational, liquidity, concentration, tail and hard-risk checks.
13. Build and persist canonical `KeelState`.
14. Compute the permanent deterministic baseline action.
15. In shadow or authorised modes, obtain a model proposal for the same state.
16. Validate the proposal against the exact model-specific `AuthorityGrant`.
17. Select the applied action according to deployment mode.
18. Re-run final risk checks after reductions.
19. Generate idempotent `OrderIntent` records.
20. Persist state, decisions and intents atomically before submission.
21. Submit to Alpaca paper and persist acknowledgements.
22. Process partial fills, rejects, cancels and unknown outcomes.
23. Confirm broker-side protective coverage for actual filled quantity.
24. Reconcile again and emit incidents for discrepancies.
25. Build forward outcomes and counterfactual episodes offline.

No order submission occurs before steps 1–20 succeed.

## 5. Core domain records

- `Instrument`, `SymbolAlias`, `ListingPeriod`, `CorporateAction`
- `UniverseDefinition`, `UniverseSnapshot`
- `MarketDataManifest`, `DataQualityReport`
- `FeatureDefinition`, `FeatureSnapshot`, `Signal`
- `StrategyDecision`, `PortfolioProposal`, `RiskDecision`
- `KeelState`, `KeelActionProposal`, `ValidatedKeelAction`
- `AuthorityGrant`, `ModelBundle`
- `OrderIntent`, `BrokerOrder`, `Fill`, `PositionSnapshot`
- `ReconciliationResult`, `Incident`
- `Hypothesis`, `ExperimentRun`
- `DeploymentCandidate`, `CertificationRecord`, `Deployment`
- `KeelEpisode`, `ForwardValidationReport`

Every persisted record has a stable ID, schema version, creation time, as-of time where relevant, provenance and content hash.

## 6. Deployment candidate

A candidate freezes the complete adaptive process:

- source commit and dependency lock;
- data and universe manifests;
- feature and normalisation versions;
- strategy roster and parameters;
- selector/meta-policy;
- qualitative policy and failure mode;
- allocator and portfolio construction;
- hard and configured risk policy;
- cost, slippage and execution model;
- strategy lifecycle/decay policy;
- exchange calendar and session rules;
- random seeds and validation plan.

Changing any field creates a new candidate ID. Certification never mutates a candidate.

## 7. Research and certification protocol

Lifecycle:

```text
IDEA → HYPOTHESIS → EXPERIMENT PLAN → DEVELOPMENT
→ NESTED WALK-FORWARD → COMPLETE-CANDIDATE VALIDATION
→ SEALED HOLDOUT → CANDIDATE FROZEN
→ SHADOW LIVE → ALPACA PAPER → FORWARD VALIDATION
→ LIMITED AUTHORITY REVIEW → ACTIVE / THROTTLED / QUARANTINED / RETIRED
```

Mandatory controls:

- permanent hypothesis and multiple-testing registry;
- purge and embargo derived from feature and label horizons;
- outer folds evaluate the full selection process;
- multiple null models, not one convenient bootstrap;
- effective independent-bet count rather than raw trade count;
- confidence intervals and tail metrics;
- cost, spread, slippage, gap and capacity stress;
- stability by time, symbol, regime, sector and factor;
- parameter-neighbourhood stability;
- sealed holdout used once per candidate lineage;
- predetermined forward-paper statistical and operational thresholds.

Required reports include return, volatility, Sharpe, Sortino, Calmar, maximum drawdown and duration, expected shortfall, worst day/trade, turnover, exposure, trade clusters, capacity, factor exposure, regime breakdown, cost sensitivity and confidence intervals.

The status vocabulary is:

```text
RESEARCH_INVALID
RESEARCH_INSUFFICIENT
HISTORICALLY_VALIDATED
SEALED_HOLDOUT_PASSED
PAPER_FORWARD_VALIDATING
PAPER_FORWARD_PASSED
OPERATIONALLY_UNSAFE
READY_FOR_AUTHORITY_REVIEW
```

## 8. Keel Intelligence

### 8.1 Model bundle

```text
state encoder
world/outcome model
strategy-applicability model
anomaly ensemble
bounded policy model
calibration layer
optional narrator with zero authority
```

The model receives structured market, candidate, strategy, portfolio, execution, operational and evidence state. It returns only enumerated postures, bounded participation/position multipliers, strategy permissions, candidate permissions, operational requests, confidence, uncertainty, anomaly score and controlled reason codes.

It never returns order quantity, price, arbitrary code, tool calls or prose instructions to execution.

### 8.2 Authority ladder

```text
K0 research only
K1 observer
K2 narrator
K3 shadow policy
K4 advisory policy
K5 reduction-only authority
K6 certified strategy-routing authority
K7 bounded allocation authority
```

Authority is granted to one exact model bundle, state/action schema pair, deployment candidate and evidence period. It expires. No level permits changing hard limits, broker endpoints, model weights, certification or authority.

### 8.3 Learning

Training data is a structured `KeelEpisode`:

- exact state and data vintage;
- legal actions;
- permanent baseline action;
- model proposal and applied action;
- predicted outcome distributions;
- observed outcomes at multiple horizons;
- counterfactual estimates and credibility;
- data quality, operational integrity and attribution quality;
- candidate, model and authority identifiers.

Training stages:

1. schema and invariant competence;
2. self-supervised Keel-state representation;
3. outcome and incident prediction;
4. deterministic baseline imitation;
5. bounded action ranking;
6. sealed offline policy evaluation;
7. live shadow comparison;
8. limited, expiring authority.

A raw equity move is not a valid label for model quality. Evaluation is incremental against the deterministic baseline using return, drawdown, expected shortfall, turnover, opportunity cost, false-defensive rate and operational exposure.

## 9. Authority gate

Every model proposal is untrusted input. The gate verifies:

- state ID and schema match;
- model bundle, candidate and authority profile match;
- grant is active and unexpired;
- state completeness meets the grant threshold;
- broker is reconciled;
- no position is unprotected;
- proposed posture and operational action are permitted;
- participation and position multipliers are inside grant ceilings;
- strategy actions refer only to certified strategies present in state;
- proposal is not stale or replayed;
- hard risk and operational invariants still pass.

A failed proposal produces a deterministic safe fallback and a reason-coded violation event. It never partially applies an invalid proposal.

## 10. Execution state machines

Order lifecycle:

```text
CREATED → PERSISTED → SUBMITTING → ACKNOWLEDGED
→ PARTIALLY_FILLED → FILLED
SUBMITTING → REJECTED / UNKNOWN
ACKNOWLEDGED or PARTIALLY_FILLED → CANCEL_PENDING
→ CANCELLED / EXPIRED / UNKNOWN
```

Position/protection lifecycle:

```text
NO_POSITION → ENTRY_PENDING → POSITION_UNPROTECTED
→ PROTECTION_PENDING → POSITION_PROTECTED
→ EXIT_PENDING → FLAT_CONFIRMED
```

`POSITION_UNPROTECTED`, broker mismatch or unknown write outcome blocks new entries and raises an incident.

Client order IDs encode deployment, session, strategy, stable instrument ID, signal timestamp and logical attempt. Retries preserve the logical intent identity.

## 11. Persistence and audit

Use SQLite in WAL mode initially, with foreign keys and migrations. Transactional tables include deployments, candidates, certifications, models, grants, state/action decisions, order intents, broker orders, fills, positions, reconciliation runs, incidents, event cursors and episode metadata.

Use content-addressed immutable artefacts for raw/curated market data, features, experiments, evidence bundles, model weights, normalisation, calibration and episode datasets.

The canonical event ledger is hash chained:

```text
record_hash = SHA256(previous_hash || canonical_record)
```

Every event includes monotonic sequence, wall and broker timestamps, process instance, deployment/candidate/model IDs, correlation and causation IDs, provenance and the previous hash.

## 12. Startup and crash recovery

1. Acquire a single-instance lock.
2. Verify configuration, candidate, certification, model and artefact hashes.
3. Verify exact Alpaca paper account identity and paper-only hostname.
4. Open the database and run approved migrations.
5. Verify the journal chain from its latest checkpoint.
6. Load the active candidate and applicable authority grant.
7. Run model self-test vectors.
8. Query broker clock, account, orders, fills and positions.
9. Reconcile desired, expected and observed states.
10. Repair only deterministic, safe discrepancies.
11. Block on ambiguous discrepancies.
12. Enter shadow, active-paper, exits-only or halted mode.
13. Permit entries only after every readiness gate passes.

Forced termination at any instruction boundary must not create a duplicate order after restart.

## 13. Session and kill workflows

Session state:

```text
BOOTING → RECONCILING → READY → MARKET_OPEN
→ ENTRY_CUTOFF → FLATTENING_INTRADAY
→ VERIFYING_SESSION_STATE → MARKET_CLOSED
```

Runtime mode:

```text
DISARMED
SHADOW
ACTIVE_PAPER
DEGRADED_EXITS_ONLY
HALTED
KILL_REQUESTED
VERIFYING_FLAT
FLAT_CONFIRMED
KILL_FAILED
```

Kill disables entries, requests cancellation, requests liquidation, repeatedly reconciles broker state, and reports only `FLAT_CONFIRMED`, `PARTIALLY_FLAT`, `KILL_FAILED` or `UNKNOWN_BROKER_STATE`. Request success is not flatten success.

## 14. Qualitative/event layer

The event layer can never create an entry. Each candidate declares one mode:

- `OPTIONAL_BASELINE`: overlay failure reverts to the quantitatively certified baseline.
- `CERTIFICATION_REQUIRED`: overlay failure blocks affected entries.

The overlay is evaluated as a policy for avoided losers, missed winners, participation, sample size, tail risk, drawdown and net outcome. “Veto only” is a safety boundary, not proof of value.

## 15. Security

- exact allowlist of the Alpaca paper hostname;
- dedicated paper credentials and startup account verification;
- secrets excluded from logs, model state, events and evidence bundles;
- least-privilege process and file access;
- immutable/hash-verified config and model artefacts;
- loopback-only UI by default; authenticated access when exposed;
- no broker credentials available to model or teacher services;
- dependency lock, SBOM and vulnerability scan for releases;
- live trading implemented only in a separate reviewed repository/build profile.

## 16. Observability

Required metrics and alerts:

- market-data age, gaps and data-quality severity;
- state-build, baseline and model latency;
- anomaly, disagreement and calibration drift;
- authority rejection and fallback counts;
- order submit/ack/fill latency and reject rate;
- expected versus realised slippage;
- stale and unknown orders;
- unprotected positions and protection mismatch;
- reconciliation discrepancies;
- journal/database failures;
- portfolio, strategy, sector, factor and correlation risk;
- process restarts and unresolved incidents.

## 17. User surfaces

The monitor shows active deployment/candidate/certification/model/grant, authority expiry, data quality, broker reconciliation, protection status, baseline/model/applied actions, reason codes, risk and stress, incidents, strategy lifecycle and forward-validation status.

Audited controls are limited to pause/resume entries, reconcile, flatten one symbol, kill and verify, revoke AI authority, switch to deterministic baseline/shadow, request strategy quarantine and export evidence. No control changes hard limits or enables live money.

Target CLI groups:

```text
keel data ...
keel research ...
keel candidate ...
keel certify ...
keel deploy ...
keel runtime ...
keel reconcile ...
keel incident ...
keel intelligence ...
keel evidence ...
keel doctor ...
```

## 18. Build programme

### Epic 0 — Truth baseline

- pin the current commit and dependency environment;
- reproduce all tests and CI claims;
- map every architectural claim to code, tests and evidence;
- capture an end-to-end current runtime trace;
- register known contradictions and unsafe assumptions.

Exit: every material current-state claim has evidence or is explicitly downgraded.

### Epic 1 — Canonical contracts

- land `KeelState`, `KeelActionProposal`, `AuthorityGrant`, `KeelEpisode` and reason codes;
- add deterministic baseline and authority validator;
- adapt current runtime status into state v1;
- run current LLM only in shadow through the same strict contract.

Exit: no free-form model output can affect runtime state.

### Epic 2 — Durable execution core

- SQLite migrations and repositories;
- order-intent idempotency;
- broker order/fill lifecycle;
- startup reconciliation and crash recovery;
- protection verification;
- session and kill state machines;
- structured incidents and metrics.

Exit: forced restart tests create no duplicate or orphaned order intent.

### Epic 3 — Data and research reproducibility

- stable instrument/security master;
- point-in-time universe snapshots;
- corporate-action and exchange-calendar policy;
- immutable data/feature manifests;
- feature registry and leakage tests;
- permanent hypothesis/experiment registry.

Exit: a clean machine reproduces a run from manifests.

### Epic 4 — Complete-candidate simulator and certification

- unify historical/live domain policy;
- freeze full `DeploymentCandidate`;
- nested walk-forward, purge/embargo and multiple nulls;
- effective sample, factor, capacity and tail reports;
- sealed holdout governance and evidence bundles.

Exit: certification applies to the complete deployable process.

### Epic 5 — Portfolio risk

- liquidity/participation limits;
- planned stop, stressed gap and notional loss;
- sector/factor/correlation/strategy concentration;
- expected shortfall and scenario stress;
- explicit daily loss and operational halt semantics.

Exit: individually valid trades cannot form an invalid portfolio.

### Epic 6 — Structured episode factory

- multi-horizon outcomes;
- permanent baseline counterfactual;
- simulated alternatives and credibility scores;
- dataset manifests and temporal split enforcement;
- data/operational/attribution quality weights.

Exit: model training no longer uses adjacent equity direction as truth.

### Epic 7 — Native Keel models

- operational anomaly detector first;
- strategy-applicability ranker;
- reduction-only posture policy;
- calibrated uncertainty and OOD detection;
- champion/challenger registry and frozen inference bundle.

Exit: K3 shadow model is reproducible, calibrated and safer than prompt-only control.

### Epic 8 — Forward paper validation

- shadow live collection;
- Alpaca paper deployment with no protocol changes inside evaluation blocks;
- expected/realised slippage and operational SLO comparison;
- predetermined pass/fail report.

Exit: forward evidence and operational integrity meet the frozen plan.

### Epic 9 — Limited authority

- issue model-specific, expiring K5 grant;
- reduction-only application with permanent baseline comparison;
- automatic revocation on calibration, OOD, incident or evidence thresholds;
- independent review of authority violations and opportunity cost.

Exit: authority is evidence-backed, bounded, reversible and fully attributable.

## 19. Immediate implementation slice

The first code slice belongs under `src/keel/intelligence/` and must provide:

- immutable contracts and enums;
- controlled reason-code vocabulary;
- deterministic baseline;
- pure authority validator;
- conservative legacy status adapter;
- structured episode record;
- tests for grant expiry, wrong model/candidate/state, broker mismatch, unprotected positions, incomplete state, strategy scope and multiplier escalation.

It must not yet be wired to broker writes. Initial integration mode is K3 shadow.

## 20. Definition of done for Keel v1

Keel v1 is complete only when:

1. A clean machine reproduces candidates and evidence bundles from manifests.
2. Historical and paper decisions use the same domain policy code.
3. The active candidate is immutable and traceable to commit/config/data.
4. Forced termination and restart cannot duplicate logical orders.
5. Broker orders, fills, positions and protection continuously reconcile.
6. Kill produces broker-confirmed terminal status.
7. Every decision records baseline, model proposal, validation and applied action.
8. No model acts without an exact, active, non-expired grant.
9. Every active strategy and model has applicable certification evidence.
10. Forward paper operation meets predetermined statistical and operational gates.
11. Every order can be explained from original state through broker fill.
12. Schemas, tests, docs and generated artefacts agree on versioned truth.

Until all twelve are met, Keel remains a research and development paper system, regardless of how convincing a backtest or AI explanation appears.

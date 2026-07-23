# Research Bets

The only status file. Each bet is falsifiable, has a deadline, and ends in
CLEARED or KILLED — no third state, no indefinite deferral. While a bet is
open, no new infrastructure is built.

Verdict standard for CLEARED: out-of-sample block-bootstrap p-value that
survives Benjamini–Hochberg across *all* variants tried for the bet, at
realistic costs, on a point-in-time universe.

See `VISION.md` for where these bets are heading and `ROADMAP.md` for the gates
each phase must clear.

## Open

*(none — v0.1 is plumbing; open the first bet before writing any new code)*

## Candidate bets (pick one, date it, move it to Open)

### Phase 1 — prove the harness on a known effect
1. **Cross-sectional equity momentum**, monthly, on a hand-built
   survivorship-free PIT index-constituent list. *This is the calibration bet:*
   a known anomaly must show up cleanly before we trust the harness on anything
   novel. Do this one first.
2. **Overnight vs intraday return decomposition** on liquid large caps.
3. **Post-earnings announcement drift**, event-window entries only.

### Phase 2 — diversified risk premia (the realistic core)
4. **Multi-asset time-series trend following** (managed-futures style) across
   equity index, rates, FX, and commodity futures — the diversifying premium a
   small operator can actually harvest.
5. **Cross-asset carry** (FX carry, futures roll yield).
6. **Volatility risk premium**, systematically and *with* a defined tail hedge —
   never naked. Tail risk is the whole story here.

### Crypto (first accessible live venue)
7. **Perpetual-futures funding-rate harvest** / cash-and-carry basis on a major
   crypto venue — less efficient market, real premium, real counterparty and
   operational risk to model honestly.

## Closed

*(none yet)*

# Prometheus v2 Threat Model – Adversary View (Red-Team Perspectives)

> **Important:** This document is for **threat modeling and defensive design only.** It describes how powerful market participants *might* behave in ways that are harmful to weaker participants, so that Prometheus can detect and protect against such situations. It is **not** an instruction manual for illegal or manipulative behavior.

## 1. Purpose

- Model plausible **adversary behaviors** at two scales:
  - A very large actor (billionaire / mega-fund, “Soros-scale”).
  - A mid-sized systematic fund with ~USD 1M deployable capital.
- Understand **how their behavior could harm us** if we are a soft target.
- Turn these insights into **defensive requirements** and synthetic scenarios.

We stay at a conceptual level and avoid specific manipulative tactics.

---

## 2. Adversary A – Large Global Macro Actor ("Soros-scale")

### 2.1 Capabilities and constraints

- Capital in billions, plus leverage via derivatives and funding markets.
- Deep access to:
  - OTC markets.
  - Prime brokers and large dealer balance sheets.
  - Information and research (macro, policy, flows).
- Can influence prices in less liquid markets by **shifting significant size**.
- Strong legal/compliance teams; will avoid explicit market manipulation but may run highly aggressive macro trades.

### 2.2 How such an actor could hurt a smaller systematic fund

From our perspective, they are dangerous when:

1. **Their macro trades align against our crowded positions**
   - If we are in popular trades (risk parity, carry, trend) and a mega-fund takes the other side in size, they can:
     - Accelerate a regime shift (e.g., crash in a carry regime).
     - Trigger risk-management cascades among funds like us.

2. **They exploit structural fragilities in a regime we are slow to detect**
   - Example pattern (abstract): rates/fx/credit relationships become unsustainable; a large actor leans hard on the weak link.
   - If our Regime + Stability Engines are late, we may keep trading as if the old regime holds.

3. **They move liquidity in markets we treat as stable**
   - A big macro fund can drain/shift liquidity across venues or time zones.
   - If our execution assumes stable depth/spreads, our impact and slippage spike when their flows hit.

### 2.3 Defensive implications for Prometheus

- **Regime Engine**
  - Should incorporate joint text+numeric signals that pick up **policy / macro narrative shifts** early.
  - When text and prices both look like historical "big macro plays", reduce reliance on prior regime statistics.

- **Stability & Black Swan Engines**
  - Include features for **top-down liquidity** and cross-asset contagion:
    - If major indices, FX pairs, and credit all move in stress patterns simultaneously, treat it as a possible large-player-driven move.
  - Scenario sets should explicitly include episodes where:
    - Popular carry/levered trades unwind violently.

- **Assessment & Universe**
  - Recognize when certain trades are highly crowded historically; be cautious about joining them late.

- **Portfolio & Risk**
  - Ensure position sizing and leverage are such that a large macro move **against** us cannot cause forced liquidation.

---

## 3. Adversary B – Mid-Sized Systematic Fund (~1M USD)

### 3.1 Capabilities and constraints

- Capital on the order of 1M (possibly levered), not enough to move major indices.
- Likely to operate in:
  - Smaller caps, niche futures, options, or specific venues.
  - Shorter time frames and microstructure edges.
- Limited access to deep OTC markets, but can still:
  - Subscribe to data.
  - Co-locate or use fast execution services.

### 3.2 How such a fund could harm us

Given their limited size, they are more likely to:

1. **Exploit naive execution patterns**
   - If our trades are easily inferable in time/venue/size, they may:
     - Trade ahead in the same direction and exit into our volume (adverse selection).
     - Step away from the book when we trade, widening our realized spread.

2. **Exploit information processing delays**
   - If we use slower or coarse text processing, a small fund with sharper NLP/feature engineering can:
     - React to news faster and in a more nuanced way.
     - Make our signals stale and leave us providing liquidity to them.

3. **Take opportunistic opposite side of our risk-reduction flows**
   - If we cut positions mechanically when certain numeric triggers hit, and that is predictable, they can:
     - Wait for our predictable selling and then buy after we’re done, capturing mean-reversion.

### 3.3 Defensive implications for Prometheus

- **Execution design**
  - Avoid rigid, predictable patterns (e.g., always trading at specific times or fixed sizes).
  - Continuously estimate and monitor impact and slippage vs expectations.

- **Assessment & Regime**
  - Reduce latency and coarseness in text & numeric features where it matters, so we’re not systematically behind.

- **Meta-Orchestrator**
  - Include metrics on whether realized costs or short-term P&L consistently look like we’re being "picked off" around our trades.

---

## 4. Encoding "Attacker" Behaviors as Scenarios

We do **not** want Prometheus to act like these adversaries, but we can:

1. **Build synthetic scenarios** where:
   - Liquidity drops more than historical norms when we trade (execution predation).
   - Regime changes are sharper and aligned against our existing positions.
   - Volatility and spreads behave like past episodes suspected of crowding/flow-driven moves.

2. **Test engines under these scenarios**
   - Regime & Stability: do they flag stress early enough?
   - Assessment: do signals shut down or de‑risk appropriately?
   - Portfolio & Risk: do leverage and position sizes remain survivable?
   - Meta-Orchestrator: does it downgrade configs that are fragile in these adversarial worlds?

3. **Define vulnerability metrics**
   - "How much does our P&L or risk profile degrade under adversarial flows compared to historical stresses?"
   - Use this as a robustness criterion when approving configs.

---

## 5. Ethical and Regulatory Boundaries

Even when thinking from an "attacker" viewpoint for robustness:

- Prometheus must **not** be designed or used to:
  - Manipulate markets.
  - Intentionally trigger distress for specific counterparties.
  - Spread misinformation.
- The adversary perspectives exist solely to:
  - Understand how large and small aggressive participants might create environments that hurt us.
  - Ensure our engines detect and adapt to such environments.

By keeping these perspectives in a dedicated threat-modeling doc, we sharpen the defensive design of Prometheus v2 without crossing into unethical or illegal strategy design.

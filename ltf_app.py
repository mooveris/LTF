"""
LTF Decision Tool
A standalone Streamlit app that scores trade setups against the LTF framework:
- 7-Layer Cluster Score (weak / moderate / strong / elite)
- 5-Condition Execution Gate (all must pass)
- Go / No-Go verdict
- Logs every evaluated setup to a local CSV for later review

Run locally:    streamlit run ltf_app.py
Deploy:         push to GitHub -> Streamlit Community Cloud
"""

import os
from datetime import datetime
import pandas as pd
import streamlit as st

# --- Config ---
LOG_FILE = "ltf_evaluations.csv"

st.set_page_config(page_title="LTF Decision Tool", page_icon="⚖️", layout="centered")
st.title("LTF Decision Tool")
st.caption("7-Layer Cluster Score + 5-Condition Gate. Standalone. No live data feeds.")


# --- Scoring functions ---
def cluster_score(inputs: dict) -> tuple[int, str, dict]:
    """Return (total, bucket, breakdown) per the 7-layer additive rules."""
    breakdown = {
        "GEX wall present (+3)":          3 if inputs["gex_wall"] else 0,
        "OI wall present (+2)":           2 if inputs["oi_wall"] else 0,
        "Dark-pool anchor (+2)":          2 if inputs["dark_pool"] else 0,
        "VWAP aligned (+1)":              1 if inputs["vwap_aligned"] else 0,
        "Prior reactions confirmed (+N)": min(inputs["reactions"], 5),  # cap at 5
        "DEX transition zone (+1)":       1 if inputs["dex_transition"] else 0,
        "Volume profile node (+1)":       1 if inputs["volume_node"] else 0,
    }
    total = sum(breakdown.values())
    if total <= 3:
        bucket = "WEAK (skip)"
    elif total <= 6:
        bucket = "MODERATE (needs flow confirmation)"
    elif total <= 9:
        bucket = "STRONG (run the gate)"
    else:
        bucket = "ELITE (full-size, rare)"
    return total, bucket, breakdown


def evaluate_gates(inputs: dict, total_score: int) -> list[tuple[str, bool, str]]:
    """Return list of (gate_name, passed, reason) for the 5-Condition Gate."""

    # Gate 1: cluster has GEX + OI minimum
    g1 = inputs["gex_wall"] and inputs["oi_wall"]
    g1_reason = "GEX + OI both present" if g1 else "Missing GEX or OI (one signal is noise)"

    # Gate 2: DTE <= 5 OR catalyst within 24h
    g2 = (inputs["dte"] <= 5) or inputs["catalyst_24h"]
    g2_reason = (
        f"Time pressure active (DTE={inputs['dte']}"
        + (", catalyst<24h" if inputs["catalyst_24h"] else "")
        + ")"
    ) if g2 else f"No time pressure (DTE={inputs['dte']}, no catalyst)"

    # Gate 3: level tested 3+ times, OR first-touch reserved for elite (score 10+)
    if inputs["reactions"] >= 3:
        g3, g3_reason = True, f"Level tested {inputs['reactions']}x and respected"
    elif inputs["reactions"] == 0 and total_score >= 10:
        g3, g3_reason = True, "First-touch allowed (ELITE cluster, score 10+)"
    else:
        g3, g3_reason = False, (
            f"Only {inputs['reactions']} prior reactions; need 3+ "
            "(or ELITE cluster for first-touch)"
        )

    # Gate 4: GEX regime matches trade direction
    # positive GEX -> fades only (long at support / short at resistance — mean reversion)
    # negative GEX -> momentum only (long at breakout / short at breakdown)
    regime = inputs["gex_regime"]
    side = inputs["level_side"]        # "support" or "resistance"
    direction = inputs["direction"]    # "long" or "short"

    if regime == "positive":
        # fading: long at support, short at resistance
        valid = (side == "support" and direction == "long") or \
                (side == "resistance" and direction == "short")
        g4 = valid
        g4_reason = (
            f"Positive GEX -> fades only. {direction.upper()} at {side} is "
            + ("VALID" if valid else "INVALID (direction misread)")
        )
    else:  # negative GEX -> momentum
        valid = (side == "support" and direction == "short") or \
                (side == "resistance" and direction == "long")
        g4 = valid
        g4_reason = (
            f"Negative GEX -> momentum only. {direction.upper()} at {side} is "
            + ("VALID" if valid else "INVALID (counter-trend in momentum regime)")
        )

    # Gate 5: flow confirms in 5-15 min before entry
    g5 = inputs["flow_confirms"] == "yes"
    g5_reason = {
        "yes": "Flow confirmed (sweeps / premium / dark-pool aligned)",
        "no":  "Flow does NOT confirm direction",
        "unknown": "Flow read unavailable — treat as fail",
    }[inputs["flow_confirms"]]
    if inputs["flow_confirms"] == "unknown":
        g5 = False

    return [
        ("Gate 1: GEX + OI minimum",       g1, g1_reason),
        ("Gate 2: Time pressure active",   g2, g2_reason),
        ("Gate 3: Frequency confirmed",    g3, g3_reason),
        ("Gate 4: GEX regime matches",     g4, g4_reason),
        ("Gate 5: Flow confirms",          g5, g5_reason),
    ]


def verdict(bucket: str, gates: list) -> tuple[str, str]:
    """Return (verdict, size_tier)."""
    all_pass = all(g[1] for g in gates)
    eligible = bucket.startswith(("STRONG", "ELITE"))

    if not eligible:
        return "NO-GO", "NONE"
    if not all_pass:
        return "NO-GO", "NONE"
    if bucket.startswith("ELITE"):
        return "GO", "HIGH"
    return "GO", "MODERATE"


def log_evaluation(row: dict) -> None:
    """Append the evaluation to a CSV log."""
    df = pd.DataFrame([row])
    if os.path.exists(LOG_FILE):
        df.to_csv(LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(LOG_FILE, index=False)


# --- UI: inputs ---
st.subheader("Setup inputs")

col1, col2 = st.columns(2)
with col1:
    level_price = st.number_input("Level price (ES)", min_value=0.0, value=5000.0, step=0.25)
    direction = st.radio("Trade direction", ["long", "short"], horizontal=True)
    level_side = st.radio("Level side", ["support", "resistance"], horizontal=True)
    gex_regime = st.radio("Net GEX regime", ["positive", "negative"], horizontal=True)
    dte = st.number_input("DTE to nearest major expiry", min_value=0, max_value=60, value=2)
    catalyst_24h = st.checkbox("Catalyst within 24h (FOMC/CPI/NFP/earnings)")

with col2:
    st.markdown("**Cluster components present at level:**")
    gex_wall = st.checkbox("GEX wall (+3)")
    oi_wall = st.checkbox("OI wall (+2)")
    dark_pool = st.checkbox("Dark-pool anchor (+2)")
    vwap_aligned = st.checkbox("VWAP aligned (+1)")
    dex_transition = st.checkbox("DEX transition zone (+1)")
    volume_node = st.checkbox("Volume profile node (+1)")
    reactions = st.number_input(
        "Prior confirmed reactions at this level",
        min_value=0, max_value=10, value=0,
        help="Each adds +1 to cluster score (capped at 5). First-touch (0) only allowed for ELITE clusters."
    )

flow_confirms = st.radio(
    "Flow read (5-15 min before entry)",
    ["yes", "no", "unknown"],
    horizontal=True,
    help="Sweeps / net premium / dark-pool activity aligned with trade direction"
)

note = st.text_input("Optional note (regime, context, gut read)")

# --- Evaluate ---
if st.button("Evaluate setup", type="primary"):
    inputs = {
        "gex_wall": gex_wall, "oi_wall": oi_wall, "dark_pool": dark_pool,
        "vwap_aligned": vwap_aligned, "dex_transition": dex_transition,
        "volume_node": volume_node, "reactions": int(reactions),
        "dte": int(dte), "catalyst_24h": catalyst_24h,
        "gex_regime": gex_regime, "level_side": level_side,
        "direction": direction, "flow_confirms": flow_confirms,
    }

    total, bucket, breakdown = cluster_score(inputs)
    gates = evaluate_gates(inputs, total)
    final_verdict, size = verdict(bucket, gates)

    # --- Display ---
    st.divider()
    st.subheader("Cluster Score")
    st.metric(label=f"Total ({bucket})", value=total)
    with st.expander("Score breakdown"):
        for k, v in breakdown.items():
            st.write(f"- {k}: **{v}**")

    st.subheader("5-Condition Gate")
    for name, passed, reason in gates:
        icon = "✅" if passed else "❌"
        st.write(f"{icon} **{name}** — {reason}")

    st.divider()
    st.subheader("Verdict")
    if final_verdict == "GO":
        st.success(f"### GO — Size: {size}")
    else:
        st.error(f"### NO-GO — Size: {size}")
        # explain why
        reasons = []
        if not bucket.startswith(("STRONG", "ELITE")):
            reasons.append(f"cluster is {bucket}, need STRONG or ELITE")
        failed_gates = [g[0] for g in gates if not g[1]]
        if failed_gates:
            reasons.append("failed: " + ", ".join(failed_gates))
        st.write("Reasons: " + "; ".join(reasons))

    # --- Log ---
    log_row = {
        "timestamp": datetime.utcnow().isoformat(),
        "level_price": level_price, "direction": direction, "level_side": level_side,
        "gex_regime": gex_regime, "dte": dte, "catalyst_24h": catalyst_24h,
        "gex_wall": gex_wall, "oi_wall": oi_wall, "dark_pool": dark_pool,
        "vwap_aligned": vwap_aligned, "dex_transition": dex_transition,
        "volume_node": volume_node, "reactions": reactions,
        "flow_confirms": flow_confirms,
        "cluster_score": total, "bucket": bucket,
        "gate1": gates[0][1], "gate2": gates[1][1], "gate3": gates[2][1],
        "gate4": gates[3][1], "gate5": gates[4][1],
        "verdict": final_verdict, "size_tier": size,
        "note": note,
    }
    log_evaluation(log_row)
    st.caption(f"Logged to `{LOG_FILE}`")


# --- History viewer ---
st.divider()
with st.expander("View evaluation history"):
    if os.path.exists(LOG_FILE):
        hist = pd.read_csv(LOG_FILE)
        st.dataframe(hist.tail(50), use_container_width=True)
        st.download_button(
            "Download full history CSV",
            data=hist.to_csv(index=False).encode(),
            file_name="ltf_evaluations.csv",
            mime="text/csv",
        )
    else:
        st.info("No evaluations yet. Run one above.")

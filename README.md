# LTF Decision Tool

A standalone Streamlit app that gates trade setups through the LTF framework:
**7-Layer Cluster Score** + **5-Condition Execution Gate** -> Go / No-Go verdict.

No live data feeds. Manual input. Designed to mechanically block discretionary
breakdowns (most notably the resistance-side directional misread when GEX
regime and trade direction don't match).

## Files

- `ltf_app.py` - the entire app, one file
- `requirements.txt` - dependencies for Streamlit Cloud
- `ltf_evaluations.csv` - auto-created log of every evaluation

## Run locally

```bash
pip install -r requirements.txt
streamlit run ltf_app.py
```

Opens at `http://localhost:8501`.

## Deploy online (free, ~5 minutes)

1. Push these files to a **public** GitHub repo
2. Go to https://share.streamlit.io and sign in with GitHub
3. Click **"New app"**, pick your repo, set main file to `ltf_app.py`
4. Click **Deploy**
5. You get a URL like `https://your-app.streamlit.app` - bookmark it on phone + laptop

The app sleeps after ~30 min idle; first visit wakes it in ~20-30 seconds.

## Logic summary

### 7-Layer Cluster Score
| Component | Points |
|---|---|
| GEX wall | +3 |
| OI wall | +2 |
| Dark-pool anchor | +2 |
| VWAP aligned | +1 |
| Each prior reaction (capped at 5) | +1 each |
| DEX transition zone | +1 |
| Volume profile node | +1 |

Buckets: 1-3 WEAK / 4-6 MODERATE / 7-9 STRONG / 10+ ELITE.

### 5-Condition Gate (all must pass)
1. GEX + OI both present
2. DTE <= 5 OR catalyst within 24h
3. Level tested 3+ times AND respected (first-touch allowed only for ELITE)
4. GEX regime matches direction (positive GEX -> fades; negative GEX -> momentum)
5. Flow confirms direction in last 5-15 min

### Verdict
- Must be STRONG or ELITE cluster AND all 5 gates pass -> **GO**
- ELITE + all gates -> size **HIGH**, otherwise size **MODERATE**
- Anything else -> **NO-GO**, size **NONE**

## What this tool does NOT do

- Pull live data (you input what you see in MenthorQ / QuantWheel manually)
- Connect to MotiveWave or Rithmic
- Backtest the framework
- Place trades

It is a checklist with math behind it. Trade discretionary off the verdict.

## Notes

- The scoring weights are taken from the original LTF spec. They are *intuitions*,
  not calibrated. After 50+ logged evaluations, revisit them against outcomes.
- First-touch exception (reactions=0, ELITE cluster) is documented as a known
  loophole. Consider disabling it for the first 30 live trades.
- The CSV log is local to wherever the app runs. On Streamlit Cloud, the log
  resets when the container sleeps - **download it after each session** via the
  history viewer at the bottom of the app.

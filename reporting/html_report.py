"""
GitHub Pages용 HTML 리포트 생성기.
- 단일 파일 self-contained HTML
- 다크 테마 기반 대시보드 스타일
"""
from __future__ import annotations
import datetime as dt
import json
from html import escape

from engine.composite import regime_emoji, regime_ko


def _tier_of(code: str) -> int:
    t1 = {"VIX", "HY_OAS", "MOVE", "DXY", "CURVE_2s10s"}
    t3 = {"BTC_DOMINANCE", "CRYPTO_FNG", "CRYPTO_FUNDING", "STABLECOIN_MCAP"}
    t4 = {"USDKRW", "KOSPI_MOMENTUM", "KOSPI_RV20", "KOSPI_FOREIGN_NET"}
    if code in t1: return 1
    if code in t3: return 3
    if code in t4: return 4
    return 5


def _regime_color(regime: str) -> str:
    return {
        "RISK_ON":  "#16a34a",
        "NEUTRAL":  "#64748b",
        "RISK_OFF": "#dc2626",
    }.get(regime, "#64748b")


def _score_color(score: float) -> str:
    if score >= 70: return "#16a34a"
    if score >= 55: return "#84cc16"
    if score >= 40: return "#f59e0b"
    return "#dc2626"


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, 'SF Pro Display', 'Pretendard', 'Segoe UI', sans-serif;
    background: #0b1020;
    color: #e5e7eb;
    padding: 24px 16px;
    min-height: 100vh;
}
.container { max-width: 1080px; margin: 0 auto; }
header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid #1f2937;
}
h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }
.ts { font-size: 13px; color: #94a3b8; }

.hero {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 24px;
    text-align: center;
}
.hero-score { font-size: 64px; font-weight: 800; letter-spacing: -0.03em; line-height: 1; }
.hero-label { font-size: 14px; color: #94a3b8; margin-top: 8px; text-transform: uppercase; letter-spacing: 0.1em; }
.hero-regime { font-size: 22px; font-weight: 700; margin-top: 20px; }
.hero-meta { font-size: 13px; color: #94a3b8; margin-top: 12px; }

.tier-section { margin-bottom: 24px; }
.tier-title {
    font-size: 12px; font-weight: 600; color: #94a3b8;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 12px;
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
}
.card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 16px 18px;
    position: relative;
}
.card::before {
    content: ''; position: absolute; left: 0; top: 0; bottom: 0;
    width: 3px; border-radius: 12px 0 0 12px;
}
.card.on::before { background: #16a34a; }
.card.neu::before { background: #64748b; }
.card.off::before { background: #dc2626; }

.card-code { font-size: 11px; font-weight: 700; color: #94a3b8; letter-spacing: 0.05em; }
.card-name { font-size: 13px; color: #cbd5e1; margin-top: 4px; line-height: 1.4; }
.card-value { font-size: 24px; font-weight: 700; margin-top: 8px; }
.card-footer {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 10px; font-size: 11px; color: #64748b;
}
.chip {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
}
.chip.on  { background: rgba(22, 163, 74, 0.15); color: #4ade80; }
.chip.neu { background: rgba(100, 116, 139, 0.18); color: #94a3b8; }
.chip.off { background: rgba(220, 38, 38, 0.15); color: #f87171; }

footer { margin-top: 40px; text-align: center; font-size: 11px; color: #475569; }
footer a { color: #64748b; text-decoration: none; }
"""


def _card_class(regime: str) -> str:
    return {"RISK_ON": "on", "NEUTRAL": "neu", "RISK_OFF": "off"}.get(regime, "neu")


def _format_val(code: str, v) -> str:
    if v is None: return "-"
    if code in ("VIX", "MOVE", "DXY", "USDKRW", "KOSPI_RV20"): return f"{v:.2f}"
    if code == "HY_OAS": return f"{v:.2f}%"
    if code == "CURVE_2s10s": return f"{v:.1f}bp"
    if code == "BTC_DOMINANCE": return f"{v:.2f}%"
    if code == "CRYPTO_FNG": return f"{int(v)}"
    if code == "CRYPTO_FUNDING": return f"{v:.4f}%"
    if code == "STABLECOIN_MCAP": return f"${v:.1f}B"
    if code == "KOSPI_MOMENTUM": return f"{v:+.2f}%"
    if code == "KOSPI_FOREIGN_NET": return f"₩{v:+.0f}B"
    return str(v)


def _render_card(ind: dict) -> str:
    code = ind.get("code", "")
    klass = _card_class(ind.get("regime", "NEUTRAL"))
    val_str = _format_val(code, ind.get("value"))
    prev_str = f"prev {_format_val(code, ind.get('prev'))}" if ind.get("prev") is not None else ""
    z = ind.get("zscore_252d")
    z_str = f"Z={z:+.2f}" if z is not None else ""
    return f"""
    <div class="card {klass}">
      <div class="card-code">{escape(code)}</div>
      <div class="card-name">{escape(ind.get("name", ""))}</div>
      <div class="card-value">{escape(val_str)}</div>
      <div class="card-footer">
        <span class="chip {klass}">{escape(ind.get("regime", ""))}</span>
        <span>{escape(prev_str)} {escape(z_str)}</span>
      </div>
    </div>"""


def _render_tier(title: str, tier_no: int, indicators: list[dict]) -> str:
    items = [i for i in indicators if _tier_of(i["code"]) == tier_no]
    if not items:
        return ""
    cards = "\n".join(_render_card(i) for i in items)
    return f"""
    <section class="tier-section">
      <div class="tier-title">{escape(title)}</div>
      <div class="grid">{cards}</div>
    </section>"""


def build_html(composite_result, indicators: list[dict]) -> str:
    ts_kst = (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
    color = _score_color(composite_result.score)
    emoji = regime_emoji(composite_result.regime)
    regime_ko_txt = regime_ko(composite_result.regime)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Risk Regime Monitor — {ts_kst}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Risk Regime Monitor</h1>
    <span class="ts">{escape(ts_kst)}</span>
  </header>

  <div class="hero">
    <div class="hero-score" style="color:{color}">{composite_result.score:.1f}</div>
    <div class="hero-label">Composite Risk Score · 0 = Risk-Off · 100 = Risk-On</div>
    <div class="hero-regime">{emoji} {escape(regime_ko_txt)}</div>
    <div class="hero-meta">
      Coverage {composite_result.coverage * 100:.0f}% ·
      🟢 {composite_result.risk_on_count} ·
      ⚪ {composite_result.neutral_count} ·
      🔴 {composite_result.risk_off_count}
    </div>
  </div>

  {_render_tier("🔴 Tier 1 · Core Signals (Global)", 1, indicators)}
  {_render_tier("🟡 Tier 3 · Crypto Risk", 3, indicators)}
  {_render_tier("🟢 Tier 4 · Korea Market", 4, indicators)}

  <footer>
    <div>Generated by <a href="https://github.com/jinhae8971/risk-regime-monitor">risk-regime-monitor</a></div>
    <div>Not investment advice. Data may be delayed.</div>
  </footer>
</div>
</body>
</html>"""
    return html


def save_report(html: str, path: str = "docs/index.html") -> None:
    import os as _os
    _os.makedirs(_os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

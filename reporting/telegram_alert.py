"""
Telegram HTML 메시지 빌더 + 전송.
- 종합 레짐 요약
- Tier별 상세 (접힘 형식 불가하므로 순차 분할)
- 임계값 돌파 시 경고
"""
from __future__ import annotations
import os
import datetime as dt
import requests

from engine.composite import regime_emoji, regime_ko


def _send(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=20)
    r.raise_for_status()


def _regime_tag(regime: str) -> str:
    tags = {
        "RISK_ON": "🟢 ON",
        "NEUTRAL": "⚪ NT",
        "RISK_OFF": "🔴 OFF",
    }
    return tags.get(regime, "⚪ ??")


def _format_value(code: str, val) -> str:
    if val is None:
        return "-"
    if code in ("VIX", "MOVE", "DXY", "USDKRW", "KOSPI_RV20"):
        return f"{val:.2f}"
    if code == "HY_OAS":
        return f"{val:.2f}%"
    if code == "CURVE_2s10s":
        return f"{val:.1f}bp"
    if code == "BTC_DOMINANCE":
        return f"{val:.2f}%"
    if code == "CRYPTO_FNG":
        return f"{int(val)}"
    if code == "CRYPTO_FUNDING":
        return f"{val:.4f}%"
    if code == "STABLECOIN_MCAP":
        return f"${val:.1f}B"
    if code == "KOSPI_MOMENTUM":
        return f"{val:+.2f}%"
    if code == "KOSPI_FOREIGN_NET":
        return f"₩{val:+.0f}B"
    return str(val)


def build_summary_message(
    composite_result, indicators: list[dict], report_url: str | None = None
) -> str:
    """상위 요약 메시지 (1개)."""
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M KST")
    emoji = regime_emoji(composite_result.regime)
    regime_txt = regime_ko(composite_result.regime)

    lines = [
        f"<b>📊 Risk Regime Monitor</b>  <i>{ts}</i>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{emoji} <b>{regime_txt}</b>",
        f"Composite Score: <b>{composite_result.score:.1f}</b> / 100",
        f"Coverage: {composite_result.coverage * 100:.0f}%  "
        f"(On {composite_result.risk_on_count} / "
        f"Neu {composite_result.neutral_count} / "
        f"Off {composite_result.risk_off_count})",
        "",
    ]

    # Tier별로 그룹핑해 간결하게
    tier1_codes = ["VIX", "HY_OAS", "MOVE", "DXY", "CURVE_2s10s"]
    tier3_codes = ["BTC_DOMINANCE", "CRYPTO_FNG", "CRYPTO_FUNDING", "STABLECOIN_MCAP"]
    tier4_codes = ["USDKRW", "KOSPI_MOMENTUM", "KOSPI_RV20", "KOSPI_FOREIGN_NET"]

    code_to_ind = {i["code"]: i for i in indicators}

    def _section(title: str, codes: list[str]) -> list[str]:
        out = [f"<b>{title}</b>"]
        for c in codes:
            ind = code_to_ind.get(c)
            if not ind:
                continue
            val_str = _format_value(c, ind.get("value"))
            out.append(f"  {_regime_tag(ind['regime'])}  {c:<16} {val_str}")
        return out + [""]

    lines += _section("🔴 Tier 1 · Core", tier1_codes)
    lines += _section("🟡 Tier 3 · Crypto", tier3_codes)
    lines += _section("🟢 Tier 4 · Korea", tier4_codes)

    if report_url:
        lines.append(f'📑 <a href="{report_url}">Full Report</a>')

    return "\n".join(lines)


def build_alert_message(
    triggered: list[dict], indicators: list[dict]
) -> str | None:
    """
    임계값 돌파(레짐 전환) 발생 시 단일 알림.
    triggered: [{"code": ..., "from": ..., "to": ...}]
    """
    if not triggered:
        return None
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M KST")
    lines = [
        f"<b>⚠️ Regime Transition Alert</b>  <i>{ts}</i>",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    code_to_ind = {i["code"]: i for i in indicators}
    for t in triggered:
        c = t["code"]
        ind = code_to_ind.get(c, {})
        val_str = _format_value(c, ind.get("value"))
        lines.append(
            f"{c}: <b>{t['from']} → {t['to']}</b>  ({val_str})"
        )
    return "\n".join(lines)


def send_summary(
    composite_result, indicators: list[dict],
    token: str | None = None, chat_id: str | None = None,
    report_url: str | None = None,
) -> None:
    token = token or os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[telegram] credentials missing, skip")
        return
    msg = build_summary_message(composite_result, indicators, report_url)
    _send(token, chat_id, msg)


def send_alert(
    triggered: list[dict], indicators: list[dict],
    token: str | None = None, chat_id: str | None = None,
) -> None:
    token = token or os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    msg = build_alert_message(triggered, indicators)
    if msg:
        _send(token, chat_id, msg)

"""
Risk Regime Monitor — Main Orchestrator
실행 순서:
  1) 모든 tier의 지표 수집
  2) Composite Score 계산
  3) HTML 리포트 생성 (GitHub Pages용)
  4) 텔레그램 요약 전송
  5) 전일 스냅샷과 비교해 레짐 전환 감지 → 알림
  6) history.json에 오늘 스냅샷 저장 (persistence)
"""
from __future__ import annotations
import os
import sys
import json
import datetime as dt
from pathlib import Path

from collectors import tier1_core, tier3_crypto, tier4_korea
from engine import composite
from reporting import telegram_alert, html_report


HISTORY_PATH = Path("data/history.json")
REPORT_PATH = Path("docs/index.html")
GITHUB_USER = "jinhae8971"
REPO_NAME = "risk-regime-monitor"


def collect_all() -> list[dict]:
    """모든 tier의 지표를 수집해 단일 리스트로 반환."""
    all_indicators: list[dict] = []

    print("[1/3] Tier 1 (Core) collecting...")
    try:
        all_indicators += tier1_core.collect()
    except Exception as e:
        print(f"  tier1 error: {e}")

    print("[2/3] Tier 3 (Crypto) collecting...")
    try:
        all_indicators += tier3_crypto.collect()
    except Exception as e:
        print(f"  tier3 error: {e}")

    print("[3/3] Tier 4 (Korea) collecting...")
    try:
        all_indicators += tier4_korea.collect()
    except Exception as e:
        print(f"  tier4 error: {e}")

    return all_indicators


def detect_transitions(current: list[dict]) -> list[dict]:
    """전일 대비 regime 전환된 지표 리스트."""
    if not HISTORY_PATH.exists():
        return []
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not history:
        return []

    last_snapshot = history[-1]
    prev_regimes = {i["code"]: i["regime"] for i in last_snapshot.get("indicators", [])}

    transitions = []
    for ind in current:
        c = ind["code"]
        prev = prev_regimes.get(c)
        curr = ind["regime"]
        if prev and prev != curr:
            transitions.append({"code": c, "from": prev, "to": curr})
    return transitions


def save_history(indicators: list[dict], result) -> None:
    """최근 90일만 유지. GitHub Actions가 commit & push."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []

    snapshot = {
        "timestamp": dt.datetime.utcnow().isoformat(),
        "date": dt.date.today().isoformat(),
        "composite_score": result.score,
        "regime": result.regime,
        "coverage": result.coverage,
        "indicators": indicators,
    }

    # 같은 날짜 덮어쓰기 방지
    today_str = snapshot["date"]
    history = [h for h in history if h.get("date") != today_str]
    history.append(snapshot)
    history = history[-90:]  # 최근 90일

    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[history] {len(history)} snapshots saved → {HISTORY_PATH}")


def main(alert_only: bool = False) -> int:
    """
    Args:
        alert_only: True면 HTML/요약 메시지 생략, 전환 감지 알림만 발송.
                    (인트라데이 감시용 경량 실행)
    """
    print(f"=== Risk Regime Monitor · {dt.datetime.now()} ===")
    print(f"alert_only = {alert_only}\n")

    # 1. 수집
    indicators = collect_all()
    print(f"\n✓ Collected {len(indicators)} indicators")

    # 2. 스코어 계산
    result = composite.compute(indicators)
    print(f"✓ Composite Score: {result.score:.1f} ({result.regime})")
    print(f"  Coverage: {result.coverage * 100:.1f}%")

    # 3. 레짐 전환 감지
    transitions = detect_transitions(indicators)
    if transitions:
        print(f"⚠ {len(transitions)} regime transitions detected:")
        for t in transitions:
            print(f"   {t['code']}: {t['from']} → {t['to']}")

    # 4. HTML 리포트 (일간 전체 리포트 모드만)
    report_url = f"https://{GITHUB_USER}.github.io/{REPO_NAME}/"
    if not alert_only:
        html = html_report.build_html(result, indicators)
        html_report.save_report(html, str(REPORT_PATH))
        print(f"✓ HTML saved → {REPORT_PATH}")

    # 5. 텔레그램
    if alert_only:
        if transitions:
            telegram_alert.send_alert(transitions, indicators)
            print("✓ Transition alert sent")
        else:
            print("  no transitions, skip telegram")
    else:
        telegram_alert.send_summary(result, indicators, report_url=report_url)
        print("✓ Daily summary sent")
        if transitions:
            telegram_alert.send_alert(transitions, indicators)
            print("✓ Transition alert sent")

    # 6. 히스토리 저장 (일간 모드만)
    if not alert_only:
        save_history(indicators, result)

    return 0


if __name__ == "__main__":
    alert_only = "--alert-only" in sys.argv
    sys.exit(main(alert_only=alert_only))

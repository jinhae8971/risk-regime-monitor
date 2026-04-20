"""
Composite Risk Regime Scoring Engine
- 각 지표 regime을 숫자화 → 가중 평균 → 0~100 스코어
- 임계값 기반 최종 레짐 분류
"""
from __future__ import annotations
from dataclasses import dataclass


# Tier별, 지표별 가중치 (총합 = 1.0)
WEIGHTS = {
    # Tier 1 (50%)
    "VIX":           0.15,
    "HY_OAS":        0.15,
    "MOVE":          0.10,
    "DXY":           0.05,
    "CURVE_2s10s":   0.05,
    # Tier 3 Crypto (10%)
    "BTC_DOMINANCE":   0.025,
    "CRYPTO_FNG":      0.035,
    "CRYPTO_FUNDING":  0.02,
    "STABLECOIN_MCAP": 0.02,
    # Tier 4 Korea (10%)
    "USDKRW":             0.03,
    "KOSPI_MOMENTUM":     0.03,
    "KOSPI_RV20":         0.02,
    "KOSPI_FOREIGN_NET":  0.02,
    # 나머지 25%는 Tier 2/5 확장용 예비
}

REGIME_SCORES = {
    "RISK_ON": 100,
    "NEUTRAL": 50,
    "RISK_OFF": 0,
}


@dataclass
class CompositeResult:
    score: float                # 0~100
    regime: str                 # RISK_ON / NEUTRAL_ON / NEUTRAL_OFF / RISK_OFF
    coverage: float             # 가중치 커버리지 (데이터 가용성)
    breakdown: dict             # 지표별 기여도
    risk_on_count: int
    risk_off_count: int
    neutral_count: int


def classify_final(score: float) -> str:
    """최종 레짐 4단계 분류."""
    if score >= 70: return "RISK_ON"
    if score >= 55: return "NEUTRAL_ON"
    if score >= 40: return "NEUTRAL_OFF"
    return "RISK_OFF"


def compute(indicators: list[dict]) -> CompositeResult:
    """
    모든 tier의 지표 리스트를 받아 composite score 계산.
    가용 지표만으로 정규화해 coverage 반영.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    breakdown = {}
    counters = {"RISK_ON": 0, "NEUTRAL": 0, "RISK_OFF": 0}

    for ind in indicators:
        code = ind.get("code")
        regime = ind.get("regime", "NEUTRAL")
        w = WEIGHTS.get(code, 0)
        if w == 0:
            continue
        sc = REGIME_SCORES.get(regime, 50)
        weighted_sum += sc * w
        total_weight += w
        breakdown[code] = {
            "regime": regime,
            "score": sc,
            "weight": w,
            "contribution": round(sc * w, 2),
        }
        counters[regime] = counters.get(regime, 0) + 1

    # coverage: 전체 정의된 가중치 대비 실제 활용 비율
    defined_total = sum(WEIGHTS.values())
    coverage = total_weight / defined_total if defined_total > 0 else 0

    final_score = (weighted_sum / total_weight) if total_weight > 0 else 50
    final_regime = classify_final(final_score)

    return CompositeResult(
        score=round(final_score, 2),
        regime=final_regime,
        coverage=round(coverage, 3),
        breakdown=breakdown,
        risk_on_count=counters["RISK_ON"],
        risk_off_count=counters["RISK_OFF"],
        neutral_count=counters["NEUTRAL"],
    )


def regime_emoji(regime: str) -> str:
    return {
        "RISK_ON":      "🟢",
        "NEUTRAL_ON":   "🟡",
        "NEUTRAL_OFF":  "🟠",
        "RISK_OFF":     "🔴",
    }.get(regime, "⚪")


def regime_ko(regime: str) -> str:
    return {
        "RISK_ON":      "리스크온 (공격적)",
        "NEUTRAL_ON":   "중립-온 (선별적 위험선호)",
        "NEUTRAL_OFF":  "중립-오프 (방어 전환)",
        "RISK_OFF":     "리스크오프 (방어적)",
    }.get(regime, "미판정")


if __name__ == "__main__":
    # 테스트용 샘플
    sample = [
        {"code": "VIX", "regime": "RISK_ON"},
        {"code": "HY_OAS", "regime": "RISK_ON"},
        {"code": "MOVE", "regime": "NEUTRAL"},
        {"code": "DXY", "regime": "NEUTRAL"},
        {"code": "CURVE_2s10s", "regime": "RISK_ON"},
        {"code": "CRYPTO_FNG", "regime": "NEUTRAL"},
        {"code": "USDKRW", "regime": "NEUTRAL"},
        {"code": "KOSPI_MOMENTUM", "regime": "RISK_ON"},
    ]
    result = compute(sample)
    print(f"Score: {result.score}")
    print(f"Regime: {regime_emoji(result.regime)} {regime_ko(result.regime)}")
    print(f"Coverage: {result.coverage * 100:.1f}%")

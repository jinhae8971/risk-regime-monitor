"""
Tier 3 Crypto Risk Signals
- BTC Dominance, Fear&Greed, Funding Rates, ETF Flow, Stablecoin MCap
가중치 10%. 위험자산 베타 증폭기로 기능.
"""
from __future__ import annotations
import datetime as dt
from dataclasses import asdict
import requests

from .tier1_core import Indicator


CG_BASE = "https://api.coingecko.com/api/v3"
FG_BASE = "https://api.alternative.me/fng/"
BINANCE_BASE = "https://fapi.binance.com"


def _classify_btc_dominance(val: float, trend_7d: float) -> str:
    """
    Dominance 상승 = Risk-Off 로테이션 (알트 → BTC)
    Dominance 하락 = Risk-On (BTC → 알트, Altseason 조짐)
    """
    if trend_7d < -1.5: return "RISK_ON"
    if trend_7d > 1.5: return "RISK_OFF"
    return "NEUTRAL"


def _classify_fng(val: int) -> str:
    if val >= 75: return "RISK_ON"    # Extreme Greed
    if val <= 25: return "RISK_OFF"   # Extreme Fear (역설적이지만 매수기회)
    return "NEUTRAL"


def _classify_funding(avg_funding: float) -> str:
    """
    펀딩레이트 음(-) = 숏 과열/디레버리징 = 바닥 신호 (역발상 Risk-On)
    펀딩레이트 고(>0.05%) = 롱 과열 = 청산 리스크 (Risk-Off 경계)
    """
    if avg_funding < -0.01: return "RISK_OFF"   # 실제 패닉/디레버리징
    if avg_funding > 0.05: return "RISK_OFF"    # 과열
    return "NEUTRAL"


def _fetch_btc_dominance() -> tuple[float | None, float | None]:
    """CoinGecko 글로벌 마켓 데이터. 현재 dominance, 7일 변화율(%p)."""
    try:
        r = requests.get(f"{CG_BASE}/global", timeout=15)
        r.raise_for_status()
        data = r.json().get("data", {})
        current = float(data.get("market_cap_percentage", {}).get("btc", 0))
        # 7일 전 값은 글로벌 API에 없으므로 근사: market_cap_change 사용
        # 대안으로 별도 레포에서 전일 값 저장·비교 권장
        return current, None
    except Exception as e:
        print(f"[CoinGecko] global failed: {e}")
        return None, None


def _fetch_fear_greed() -> tuple[int | None, int | None]:
    """alternative.me Fear & Greed Index."""
    try:
        r = requests.get(FG_BASE, params={"limit": 2}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if len(data) >= 2:
            return int(data[0]["value"]), int(data[1]["value"])
        elif len(data) == 1:
            return int(data[0]["value"]), None
    except Exception as e:
        print(f"[F&G] failed: {e}")
    return None, None


def _fetch_funding_rates(symbols: list[str] | None = None) -> float | None:
    """Binance 주요 코인 펀딩레이트 평균 (8시간 기준, %)."""
    symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    rates = []
    for sym in symbols:
        try:
            r = requests.get(
                f"{BINANCE_BASE}/fapi/v1/premiumIndex",
                params={"symbol": sym}, timeout=10,
            )
            r.raise_for_status()
            rate = float(r.json().get("lastFundingRate", 0)) * 100
            rates.append(rate)
        except Exception as e:
            print(f"[Binance] {sym} funding failed: {e}")
    return sum(rates) / len(rates) if rates else None


def _fetch_stablecoin_mcap() -> tuple[float | None, float | None]:
    """CoinGecko stablecoin 카테고리 총 시총. 일간 변화율 포함."""
    try:
        r = requests.get(
            f"{CG_BASE}/coins/markets",
            params={
                "vs_currency": "usd",
                "category": "stablecoins",
                "per_page": 20,
                "page": 1,
            },
            timeout=15,
        )
        r.raise_for_status()
        coins = r.json()
        total = sum(c.get("market_cap", 0) or 0 for c in coins)
        # 24h 변화 평균으로 대체
        pct_changes = [c.get("market_cap_change_percentage_24h", 0) or 0 for c in coins]
        avg_change = sum(pct_changes) / len(pct_changes) if pct_changes else 0
        return total / 1e9, avg_change  # billions USD, %
    except Exception as e:
        print(f"[CoinGecko] stablecoin failed: {e}")
        return None, None


def collect() -> list[dict]:
    ts = dt.datetime.utcnow().isoformat()
    results: list[Indicator] = []

    # [1] BTC Dominance
    dom, _ = _fetch_btc_dominance()
    if dom is not None:
        # trend_7d는 별도 persistence 필요 (향후 data store 연동)
        results.append(Indicator(
            code="BTC_DOMINANCE", name="Bitcoin Dominance (%)",
            value=round(dom, 2), prev=None, zscore_252d=None,
            regime="NEUTRAL",  # 추세정보 없으면 중립
            source="CoinGecko(/global)", timestamp=ts,
        ))

    # [2] Crypto Fear & Greed Index
    fng, fng_prev = _fetch_fear_greed()
    if fng is not None:
        results.append(Indicator(
            code="CRYPTO_FNG", name="Crypto Fear & Greed Index",
            value=fng, prev=fng_prev, zscore_252d=None,
            regime=_classify_fng(fng),
            source="alternative.me", timestamp=ts,
        ))

    # [3] Avg Funding Rate (주요 4종 평균)
    funding = _fetch_funding_rates()
    if funding is not None:
        results.append(Indicator(
            code="CRYPTO_FUNDING", name="Avg Perp Funding Rate (%, 8h)",
            value=round(funding, 4), prev=None, zscore_252d=None,
            regime=_classify_funding(funding),
            source="Binance Futures", timestamp=ts,
        ))

    # [4] Stablecoin Market Cap (유동성 선행지표)
    mcap, change = _fetch_stablecoin_mcap()
    if mcap is not None:
        # 스테이블코인 시총 증가 = 사이드라인 자본 대기 → 잠재 Risk-On
        regime = "RISK_ON" if (change or 0) > 0.5 else "NEUTRAL"
        results.append(Indicator(
            code="STABLECOIN_MCAP", name="Stablecoin Total MCap ($B)",
            value=round(mcap, 2), prev=None, zscore_252d=None,
            regime=regime,
            source="CoinGecko(stablecoins)", timestamp=ts,
        ))

    return [asdict(r) for r in results]


if __name__ == "__main__":
    import json
    print(json.dumps(collect(), indent=2, ensure_ascii=False))

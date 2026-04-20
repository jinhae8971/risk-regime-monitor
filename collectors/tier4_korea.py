"""
Tier 4 Korea-Specific Risk Signals
- USD/KRW, KOSPI 외인수급, V-KOSPI, KOSPI200
가중치 10%. 글로벌 신호의 한국 전이 증폭기.
"""
from __future__ import annotations
import datetime as dt
from dataclasses import asdict
import yfinance as yf
import pandas as pd
import requests

from .tier1_core import Indicator, _zscore, _yahoo_series


def _classify_usdkrw(val: float) -> str:
    """한국 투자자 관점에서 환율 급등은 외인 이탈·리스크오프."""
    if val > 1480: return "RISK_OFF"
    if val < 1380: return "RISK_ON"
    return "NEUTRAL"


def _classify_vkospi(val: float) -> str:
    """V-KOSPI: KOSPI200 변동성지수. VIX 한국판."""
    if val < 15: return "RISK_ON"
    if val > 25: return "RISK_OFF"
    return "NEUTRAL"


def _classify_kospi_momentum(price: float, ma200: float) -> str:
    if pd.isna(ma200): return "NEUTRAL"
    deviation = (price - ma200) / ma200 * 100
    if deviation > 5: return "RISK_ON"
    if deviation < -5: return "RISK_OFF"
    return "NEUTRAL"


def _fetch_foreign_flow_krx() -> dict | None:
    """
    KRX 외국인 순매수 (최근 영업일).
    KRX OpenAPI 또는 krx.co.kr 직접 스크래핑.
    여기서는 pykrx 라이브러리 기반 구현 스텁.
    """
    try:
        from pykrx import stock
        today = dt.date.today().strftime("%Y%m%d")
        # 최근 영업일 투자자별 거래대금 (KOSPI)
        df = stock.get_market_trading_value_by_investor(
            today, today, "KOSPI"
        )
        if df.empty:
            # 전일 시도
            yesterday = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")
            df = stock.get_market_trading_value_by_investor(
                yesterday, yesterday, "KOSPI"
            )
        if df.empty:
            return None
        # '외국인합계' 순매수 (단위: 원)
        foreign_net = df.loc["외국인합계", "순매수"] if "외국인합계" in df.index else None
        if foreign_net is None:
            return None
        return {"foreign_net_krw_bn": round(foreign_net / 1e9, 1)}
    except ImportError:
        print("[pykrx] not installed, skip foreign flow")
        return None
    except Exception as e:
        print(f"[pykrx] foreign flow failed: {e}")
        return None


def collect() -> list[dict]:
    ts = dt.datetime.utcnow().isoformat()
    results: list[Indicator] = []

    # [1] USD/KRW
    krw = _yahoo_series("KRW=X")
    if not krw.empty:
        val = float(krw.iloc[-1])
        prev = float(krw.iloc[-2]) if len(krw) > 1 else None
        results.append(Indicator(
            code="USDKRW", name="USD/KRW Exchange Rate",
            value=round(val, 2), prev=round(prev, 2) if prev else None,
            zscore_252d=_zscore(krw), regime=_classify_usdkrw(val),
            source="Yahoo(KRW=X)", timestamp=ts,
        ))

    # [2] KOSPI 지수 + 200일 이평선 모멘텀
    kospi = _yahoo_series("^KS11", period="2y")
    if not kospi.empty and len(kospi) >= 200:
        price = float(kospi.iloc[-1])
        ma200 = float(kospi.tail(200).mean())
        prev = float(kospi.iloc[-2]) if len(kospi) > 1 else None
        results.append(Indicator(
            code="KOSPI_MOMENTUM",
            name=f"KOSPI vs 200D MA (px={price:.0f}, ma={ma200:.0f})",
            value=round((price - ma200) / ma200 * 100, 2),
            prev=round((prev - ma200) / ma200 * 100, 2) if prev else None,
            zscore_252d=_zscore(kospi),
            regime=_classify_kospi_momentum(price, ma200),
            source="Yahoo(^KS11)", timestamp=ts,
        ))

    # [3] V-KOSPI (KOSPI 변동성지수) - Yahoo ^VKOSPI 미제공, 대체: KS11 20d 실현변동성
    if not kospi.empty and len(kospi) >= 20:
        returns = kospi.pct_change().dropna()
        realized_vol = float(returns.tail(20).std() * (252 ** 0.5) * 100)
        results.append(Indicator(
            code="KOSPI_RV20", name="KOSPI 20D Realized Vol (%, ann.)",
            value=round(realized_vol, 2), prev=None,
            zscore_252d=None,
            regime=_classify_vkospi(realized_vol),
            source="Calculated(^KS11)", timestamp=ts,
        ))

    # [4] 외국인 순매수 (KRX, pykrx 선택적)
    foreign = _fetch_foreign_flow_krx()
    if foreign:
        net = foreign["foreign_net_krw_bn"]
        if net > 300: regime = "RISK_ON"
        elif net < -300: regime = "RISK_OFF"
        else: regime = "NEUTRAL"
        results.append(Indicator(
            code="KOSPI_FOREIGN_NET",
            name="KOSPI Foreign Net Buy (₩bn, 1D)",
            value=net, prev=None, zscore_252d=None,
            regime=regime,
            source="pykrx(KRX)", timestamp=ts,
        ))

    return [asdict(r) for r in results]


if __name__ == "__main__":
    import json
    print(json.dumps(collect(), indent=2, ensure_ascii=False))

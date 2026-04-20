"""
Tier 1 Core Risk Regime Signals (Yahoo Finance only, no API key needed)
- VIX, MOVE, DXY: Yahoo 직접
- HY Spread Proxy: HYG/LQD ratio (Risk vs IG ETF)
- 10Y Yield: ^TNX (Curve 인버전 신호 대체)
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, asdict
import yfinance as yf
import pandas as pd


@dataclass
class Indicator:
    code: str
    name: str
    value: float | None
    prev: float | None
    zscore_252d: float | None
    regime: str
    source: str
    timestamp: str


def _yahoo_series(ticker: str, period: str = "2y") -> pd.Series:
    """Yahoo Finance 종가 시계열."""
    try:
        data = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        if data.empty:
            return pd.Series(dtype=float)
        return data["Close"].dropna()
    except Exception as e:
        print(f"[Yahoo] {ticker} failed: {e}")
        return pd.Series(dtype=float)


def _zscore(series: pd.Series, window: int = 252) -> float | None:
    if len(series) < 30:
        return None
    s = series.tail(window)
    mu, sd = s.mean(), s.std()
    if sd == 0 or pd.isna(sd):
        return None
    return float((series.iloc[-1] - mu) / sd)


def _classify_vix(val: float) -> str:
    if val < 15: return "RISK_ON"
    if val > 25: return "RISK_OFF"
    return "NEUTRAL"


def _classify_move(val: float) -> str:
    if val < 100: return "RISK_ON"
    if val > 140: return "RISK_OFF"
    return "NEUTRAL"


def _classify_dxy(zscore: float | None) -> str:
    if zscore is None: return "NEUTRAL"
    if zscore > 1.0: return "RISK_OFF"
    if zscore < -1.0: return "RISK_ON"
    return "NEUTRAL"


def collect() -> list[dict]:
    """Tier 1 지표 5종 (모두 Yahoo Finance, 무인증)."""
    results: list[Indicator] = []
    ts = dt.datetime.utcnow().isoformat()

    # [1] VIX
    vix = _yahoo_series("^VIX")
    if not vix.empty:
        val = float(vix.iloc[-1])
        prev = float(vix.iloc[-2]) if len(vix) > 1 else None
        results.append(Indicator(
            code="VIX", name="CBOE Volatility Index",
            value=round(val, 2), prev=round(prev, 2) if prev else None,
            zscore_252d=_zscore(vix), regime=_classify_vix(val),
            source="Yahoo(^VIX)", timestamp=ts,
        ))

    # [2] MOVE
    move = _yahoo_series("^MOVE")
    if not move.empty:
        val = float(move.iloc[-1])
        prev = float(move.iloc[-2]) if len(move) > 1 else None
        results.append(Indicator(
            code="MOVE", name="ICE BofA MOVE Index",
            value=round(val, 2), prev=round(prev, 2) if prev else None,
            zscore_252d=_zscore(move), regime=_classify_move(val),
            source="Yahoo(^MOVE)", timestamp=ts,
        ))

    # [3] DXY
    dxy = _yahoo_series("DX-Y.NYB")
    if not dxy.empty:
        val = float(dxy.iloc[-1])
        prev = float(dxy.iloc[-2]) if len(dxy) > 1 else None
        z = _zscore(dxy)
        results.append(Indicator(
            code="DXY", name="US Dollar Index",
            value=round(val, 2), prev=round(prev, 2) if prev else None,
            zscore_252d=z, regime=_classify_dxy(z),
            source="Yahoo(DX-Y.NYB)", timestamp=ts,
        ))

    # [4] HY 프록시: HYG/LQD ratio (위험채권 vs 우량채권 상대성과)
    hyg = _yahoo_series("HYG", period="1y")
    lqd = _yahoo_series("LQD", period="1y")
    if not hyg.empty and not lqd.empty:
        combined = pd.concat([hyg, lqd], axis=1, keys=["HYG", "LQD"]).dropna()
        if not combined.empty:
            ratio = combined["HYG"] / combined["LQD"]
            val = float(ratio.iloc[-1])
            prev = float(ratio.iloc[-2]) if len(ratio) > 1 else None
            z = _zscore(ratio)
            if z is not None and z > 1.0:
                regime = "RISK_ON"
            elif z is not None and z < -1.0:
                regime = "RISK_OFF"
            else:
                regime = "NEUTRAL"
            results.append(Indicator(
                code="HY_OAS",
                name="HYG/LQD Ratio (Credit Risk Proxy)",
                value=round(val, 4),
                prev=round(prev, 4) if prev else None,
                zscore_252d=z, regime=regime,
                source="Yahoo(HYG,LQD)", timestamp=ts,
            ))

    # [5] 10Y Yield 추세 (2s10s 대체)
    tnx = _yahoo_series("^TNX", period="2y")
    if not tnx.empty:
        val = float(tnx.iloc[-1])
        prev = float(tnx.iloc[-2]) if len(tnx) > 1 else None
        z = _zscore(tnx)
        # 금리 급등 추세 = Risk-Off
        if z is not None and z > 1.5:
            regime = "RISK_OFF"
        elif z is not None and z < -1.0:
            regime = "RISK_ON"
        else:
            regime = "NEUTRAL"
        results.append(Indicator(
            code="CURVE_2s10s",
            name="US 10Y Treasury Yield (%)",
            value=round(val, 3),
            prev=round(prev, 3) if prev else None,
            zscore_252d=z, regime=regime,
            source="Yahoo(^TNX)", timestamp=ts,
        ))

    return [asdict(r) for r in results]


if __name__ == "__main__":
    import json
    print(json.dumps(collect(), indent=2, ensure_ascii=False))

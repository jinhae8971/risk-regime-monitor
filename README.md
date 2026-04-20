# 📊 Risk Regime Monitor

월스트리트 관점의 **5-Tier Cross-Asset Framework**로 미국·한국 주식·크립토 통합 리스크 레짐을 자동 판단·리포트하는 시스템.

---

## 🎯 Framework

| Tier | Focus | Weight | 주요 지표 |
|------|-------|--------|----------|
| 1 | Core (Global) | 50% | VIX, HY OAS, MOVE, DXY, 2s10s |
| 2 | Confirmation | 25% | IG OAS, SKEW, Momentum, Russell/SPX |
| 3 | Crypto | 10% | BTC Dominance, F&G, Funding, Stablecoin |
| 4 | Korea | 10% | USD/KRW, KOSPI 모멘텀, V-KOSPI, 외인수급 |
| 5 | Macro | 5% | PMI, Credit Impulse, GPR |

**최종 스코어 0~100** → 4단계 레짐 분류 (🟢 Risk-On / 🟡 Neutral-On / 🟠 Neutral-Off / 🔴 Risk-Off)

---

## 🏗️ Architecture

```
risk-regime-monitor/
├── collectors/          # Tier별 지표 수집
│   ├── tier1_core.py
│   ├── tier3_crypto.py
│   └── tier4_korea.py
├── engine/              # 스코어링
│   └── composite.py
├── reporting/           # 출력
│   ├── html_report.py
│   └── telegram_alert.py
├── .github/workflows/
│   ├── daily_report.yml    # 매일 07:30 / 17:00 KST
│   └── intraday_alert.yml  # 30분 간격 감시 (시장시간)
├── data/history.json    # 90일 스냅샷 (자동 업데이트)
└── docs/index.html      # GitHub Pages 리포트
```

---

## 🚀 Deployment

### 1. GitHub Secrets 등록

Repo Settings → Secrets and variables → Actions:

| Name | Value |
|------|-------|
| `TELEGRAM_TOKEN` | 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 수신 채널 |
| `FRED_API_KEY` | [FRED 무료 발급](https://fred.stlouisfed.org/docs/api/api_key.html) |

### 2. GitHub Pages 활성화

Settings → Pages → Source: `main` branch, `/docs` folder.

리포트 URL: `https://jinhae8971.github.io/risk-regime-monitor/`

### 3. 자동 실행

배포 후 워크플로우가 스케줄대로 자동 실행됩니다. 즉시 테스트는 Actions 탭에서 `workflow_dispatch`.

---

## 📡 Data Sources

| Source | 용도 | 인증 |
|--------|------|-----|
| FRED | HY OAS, IG OAS, 금리커브 | API Key |
| Yahoo Finance | VIX, MOVE, DXY, KOSPI, USD/KRW | 불필요 |
| CoinGecko | BTC dominance, stablecoin | 불필요 |
| alternative.me | Crypto F&G | 불필요 |
| Binance Futures | Funding rates | 불필요 |
| pykrx (KRX) | 외국인 순매수 | 불필요 |

---

## 📱 Output Examples

**Telegram 요약** (매일 2회)
```
📊 Risk Regime Monitor  2026-04-21 07:30 KST
━━━━━━━━━━━━━━━━━━━━━━
🟢 리스크온 (공격적)
Composite Score: 72.4 / 100
Coverage: 85%  (On 7 / Neu 4 / Off 2)

🔴 Tier 1 · Core
  🟢 ON  VIX              17.48
  🟢 ON  HY_OAS            3.02%
  ⚪ NT  MOVE              98.50
  ...
```

**GitHub Pages 대시보드**: 다크 테마 카드 뷰, Tier별 그룹핑.

---

## ⚙️ Composite Scoring Logic

```python
Score = Σ (RegimeScore_i × Weight_i) / Σ Weight_i

RegimeScore: RISK_ON=100, NEUTRAL=50, RISK_OFF=0

Final Regime:
  score ≥ 70  → RISK_ON
  score ≥ 55  → NEUTRAL_ON
  score ≥ 40  → NEUTRAL_OFF
  score < 40  → RISK_OFF
```

가용 지표만으로 정규화되므로 일부 데이터 실패 시에도 **coverage 표시와 함께 작동**합니다.

---

## 🔔 Alert Trigger

전일 스냅샷(`data/history.json`)과 비교하여 **regime 전환**이 발생한 지표만 별도 알림:

```
⚠️ Regime Transition Alert
VIX: RISK_ON → NEUTRAL  (21.34)
HY_OAS: NEUTRAL → RISK_OFF  (5.12%)
```

---

## 📝 License

MIT. Not investment advice.

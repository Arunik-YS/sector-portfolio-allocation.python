import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.optimize import minimize

st.set_page_config(page_title="2X 섹터 로테이션", layout="centered")
st.markdown("<style>.stNumberInput, .stTextInput { margin-bottom: -15px; }</style>", unsafe_allow_html=True)

# 1. 대상 자산: 미국 GICS 11대 핵심 섹터 2배(2X) 레버리지 ETF
TARGET_TICKERS = ["ROM", "UYG", "RXL", "DIG", "UXI", "UCC", "UYM", "UGE", "UPW", "URE", "LTL"]
SECTOR_NAMES = {
    "ROM": "기술 2X (Tech)",
    "UYG": "금융 2X (Financials)",
    "RXL": "헬스케어 2X (Health)",
    "DIG": "에너지 2X (Energy)",
    "UXI": "산업재 2X (Industrials)",
    "UCC": "임의소비재 2X (Discretion)",
    "UYM": "소재 2X (Materials)",
    "UGE": "필수소비재 2X (Staples)",
    "UPW": "유틸리티 2X (Utilities)",
    "URE": "부동산 2X (Real Estate)",
    "LTL": "커뮤니케이션 2X (Comm)"
}
RISK_FREE_RATE = 0.03

# 2. 데이터 분석 기간 압축: 레버리지의 휩소를 피하는 3개월(3mo) 스캐너
@st.cache_data(ttl="1d", show_spinner=False)
def fetch_momentum_data(tickers):
    df = yf.download(list(tickers), period="3mo", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        return df['Close'].dropna()
    else:
        return df[['Close']].dropna()

@st.cache_data(ttl="10m", show_spinner=False)
def get_current_prices(tickers):
    prices = {}
    df = yf.download(list(tickers), period="5d", progress=False)
    for ticker in tickers:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                valid_data = df['Close'][ticker].dropna()
            else:
                valid_data = df['Close'].dropna()
                
            if not valid_data.empty:
                prices[ticker] = float(valid_data.iloc[-1])
            else:
                prices[ticker] = 0.0
        except Exception:
            prices[ticker] = 0.0
    return prices

def portfolio_performance(weights, mean_returns, cov_matrix):
    returns = np.sum(mean_returns * weights) * 252
    std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
    return returns, std_dev, (returns - RISK_FREE_RATE) / std_dev

def negative_sharpe(weights, mean_returns, cov_matrix):
    return -portfolio_performance(weights, mean_returns, cov_matrix)[2]

# --- 백그라운드 최적화 연산 ---
tickers_tuple = tuple(TARGET_TICKERS)

with st.spinner("최근 3개월 2배수 섹터의 자금 쏠림을 스캔하고 있습니다..."):
    history_3mo = fetch_momentum_data(tickers_tuple)
    log_returns = np.log(history_3mo / history_3mo.shift(1)).dropna()
    mean_returns = log_returns.mean()
    cov_matrix = log_returns.cov()
    
    num_assets = len(TARGET_TICKERS)
    
    # 3. 비중 캡(Cap) 하향: 개별 종목 최대 30% 제한으로 레버리지 MDD 방어
    bounds = tuple((0.0, 0.3) for _ in range(num_assets)) 
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    
    opt_result = minimize(negative_sharpe, num_assets * [1./num_assets], 
                          args=(mean_returns, cov_matrix),
                          method='SLSQP', bounds=bounds, constraints=constraints)
    
    optimal_weights = {TARGET_TICKERS[i]: opt_result.x[i] for i in range(num_assets)}
    current_prices = get_current_prices(tickers_tuple)

# ==========================================
# UI 렌더링 (카테고리 역매핑 및 매드포함 버전)
# ==========================================

# 1. 경제 특성별 티커 그룹핑 정의
SECTOR_GROUPS = {
    "🚀 성장 & 기술 (Growth)": ["ROM", "LTL"],
    "🏭 경기 민감 & 순환 (Cyclical)": ["UYG", "UXI", "UCC", "URE"],
    "🛡️ 경기 방어 (Defensive)": ["RXL", "UGE", "UPW"],
    "🛢️ 물가 방어 & 원자재 (Inflation)": ["DIG", "UYM"]
}

# [핵심 추가] 티커를 넣으면 카테고리명(이모지 제외)을 반환하는 역매핑 딕셔너리 자동 생성
TICKER_TO_CATEGORY = {}
for group_name, tickers in SECTOR_GROUPS.items():
    # '🚀 성장 & 기술 (Growth)' -> '성장 & 기술'만 깔끔하게 추출
    clean_category = group_name.split(" (")[0].replace("🚀 ", "").replace("🏭 ", "").replace("🛡️ ", "").replace("🛢️ ", "")
    for t in tickers:
        TICKER_TO_CATEGORY[t] = clean_category

st.title("🚀 2X 레버리지 섹터 로테이션")
st.caption("최근 3개월 모멘텀 기반 2배수 전술적 자산 배분 (위성 계좌용)")

st.error("⚠️ **핵심-위성 전략 경고:** 레버리지 상품의 특성상 전체 투자 자산의 **20~30% 이내**의 금액만 본 시스템에 투입하는 것을 강력히 권장합니다.")

# 1. 현재 시장의 주도 섹터 결과 발표
st.subheader("🔥 이달의 2X 주도 섹터")
st.info("개별 종목 리스크를 막기 위해 한 섹터당 최대 비중은 30%로 강제 제한됩니다.")

sorted_weights = sorted(optimal_weights.items(), key=lambda x: x[1], reverse=True)
active_sectors = [(t, w) for t, w in sorted_weights if w > 0.001]

if not active_sectors:
    st.warning("현재 시장에 뚜렷한 주도 섹터가 없습니다.")
else:
    cols = st.columns(min(len(active_sectors), 4))
    for i, (ticker, weight) in enumerate(active_sectors):
        with cols[i % len(cols)]:
            sector_clean_name = SECTOR_NAMES[ticker].split(" ")[0] # '기술'
            category_name = TICKER_TO_CATEGORY.get(ticker, "") # '성장 & 기술'
            
            # [변경 포인트] st.metric의 하단 하이라이트(delta) 영역에 카테고리를 매칭하여 시각화 효과 극대화
            st.metric(
                label=f"{ticker} ({sector_clean_name})", 
                value=f"{weight*100:.1f}%",
                delta=f"[{category_name}]",
                delta_color="off" # 카테고리 텍스트에 초록색/빨간색 화살표가 붙지 않도록 일반 텍스트화
            )

st.divider()

# 2. 내 계좌 입력 (경제 그룹별 배치)
st.subheader("💼 위성 계좌 상태 입력")
shares_input = {}

for group_name, tickers_in_group in SECTOR_GROUPS.items():
    st.markdown(f"**{group_name}**")
    with st.container(border=True):
        cols = st.columns(len(tickers_in_group) if len(tickers_in_group) < 4 else 4)
        for i, ticker in enumerate(tickers_in_group):
            with cols[i % 4]:
                sector_clean_name = SECTOR_NAMES[ticker].split(" ")[0]
                input_label = f"{ticker} ({sector_clean_name})"
                shares_input[ticker] = st.number_input(input_label, min_value=0, step=1, key=f"s_{ticker}")
                
                price_display = current_prices.get(ticker, 0.0)
                st.caption(f"${price_display:.2f}")
    st.write("") 

add_cash = st.number_input("💵 리밸런싱 투입 현금 ($)", min_value=0.0, step=100.0)

# 3. 진단 및 리밸런싱 실행
if st.button("2X 섹터 리밸런싱 실행", use_container_width=True, type="primary"):
    current_values = {t: shares_input[t] * current_prices.get(t, 0.0) for t in TARGET_TICKERS}
    total_eval = sum(current_values.values())
    total_budget = total_eval + add_cash
    
    if total_budget == 0:
        st.warning("보유 주수나 추가 현금을 최소 1개 이상 입력해주세요.")
    else:
        st.subheader("📊 리밸런싱 처방전")
        st.success("💡 **매매 팁:** 밤 11시 반에 증권사 앱에서 아래 수량대로 **'LOC (종가 지정가) 예약 주문'**을 걸어두세요.")
        
        results = []
        for ticker, target_weight in sorted_weights: 
            curr_price = current_prices.get(ticker, 0.0)
            curr_weight = current_values[ticker] / total_budget if total_budget > 0 else 0
            
            clean_target_weight = 0.0 if target_weight < 0.001 else target_weight
            
            target_value = total_budget * clean_target_weight
            target_shares = target_value / curr_price if curr_price > 0 else 0
            share_diff = target_shares - shares_input[ticker]
            
            rounded_diff = round(share_diff)
            
            if rounded_diff >= 1:
                action = f"🟢 {rounded_diff}주 매수"
            elif rounded_diff <= -1:
                action = f"🔴 {abs(rounded_diff)}주 전량 매도" if clean_target_weight == 0.0 else f"🔴 {abs(rounded_diff)}주 매도"
            else:
                action = "⚪ 유지"

            if curr_weight > 0 or clean_target_weight > 0 or "매수" in action or "매도" in action:
                sector_clean_name = SECTOR_NAMES[ticker].split(" ")[0]
                category_name = TICKER_TO_CATEGORY.get(ticker, "")
                
                results.append({
                    "섹터": f"{sector_clean_name} ({ticker})", 
                    "카테고리": category_name, # 결과 표에도 매칭 레이어 추가
                    "현재 비중": f"{curr_weight*100:.1f}%",
                    "목표 비중": f"{clean_target_weight*100:.1f}%",
                    "액션 플랜": action
                })

        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        else:
            st.info("현재 자산 구조가 3개월 모멘텀에 완벽히 부합하거나, 변동 사항이 없습니다.")

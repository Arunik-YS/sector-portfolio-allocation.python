import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.optimize import minimize

st.set_page_config(page_title="섹터 로테이션 계산기", layout="centered")
st.markdown("<style>.stNumberInput, .stTextInput { margin-bottom: -15px; }</style>", unsafe_allow_html=True)

# 1. 대상 자산: 미국 11대 섹터 2배(2X) 레버리지 ETF
TARGET_TICKERS = ["ROM", "UYG", "RXL", "DIG", "UXI", "UCC", "UYM", "UGE", "UPW", "URE", "LTL"]
SECTOR_NAMES = {
    "ROM": "기술 2X (Tech)",
    "UYG": "금융 2X (Financials)",
    "RXL": "헬스케어 2X (Health)",
    "DIG": "에너지 2X (Energy)",
    "UXI": "산업재 2X (Industrials)",
    "UCC": "임의소비재 2X (Discretionary)",
    "UYM": "소재 2X (Materials)",
    "UGE": "필수소비재 2X (Staples)",
    "UPW": "유틸리티 2X (Utilities)",
    "URE": "부동산 2X (Real Estate)",
    "LTL": "커뮤니케이션 2X (Communication)"
}
RISK_FREE_RATE = 0.03 # 무위험수익률 3%

# 2. 모멘텀 측정을 위한 최근 6개월 데이터 수집 (매일 1회만 갱신)
@st.cache_data(ttl="1d", show_spinner=False)
def fetch_momentum_data(tickers):
    df = yf.download(list(tickers), period="6mo", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        return df['Close'].dropna()
    else:
        return df[['Close']].dropna()

# 3. 최근 5일 데이터로 현재가 가져오기 (결측치 방어)
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

# 4. 포트폴리오 연산 로직 (샤프지수)
def portfolio_performance(weights, mean_returns, cov_matrix):
    returns = np.sum(mean_returns * weights) * 252
    std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
    return returns, std_dev, (returns - RISK_FREE_RATE) / std_dev

def negative_sharpe(weights, mean_returns, cov_matrix):
    return -portfolio_performance(weights, mean_returns, cov_matrix)[2]

# --- 전술적 타겟 비중 백그라운드 계산 ---
tickers_tuple = tuple(TARGET_TICKERS)

with st.spinner("11개 섹터의 자금 흐름을 스캔하여 주도주를 찾고 있습니다..."):
    history_6mo = fetch_momentum_data(tickers_tuple)
    log_returns = np.log(history_6mo / history_6mo.shift(1)).dropna()
    mean_returns = log_returns.mean()
    cov_matrix = log_returns.cov()
    
    num_assets = len(TARGET_TICKERS)
    # 최소 비중 0% (가차없는 퇴출), 최대 비중 50% 제한 (분산 투자 유지)
    bounds = tuple((0.0, 0.5) for _ in range(num_assets)) 
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    
    opt_result = minimize(negative_sharpe, num_assets * [1./num_assets], 
                          args=(mean_returns, cov_matrix),
                          method='SLSQP', bounds=bounds, constraints=constraints)
    
    optimal_weights = {TARGET_TICKERS[i]: opt_result.x[i] for i in range(num_assets)}
    current_prices = get_current_prices(tickers_tuple)

# ==========================================
# UI 렌더링
# ==========================================
st.title("🏄‍♂️ 11대 섹터 모멘텀 로테이션")
st.caption("최근 6개월 시장의 자금이 쏠리는 주도 섹터를 찾아내는 추세 추종 시스템")

# 1. 현재 시장의 주도 섹터 결과 발표
st.subheader("🔥 이달의 주도 섹터 Top Pick")
st.info("모멘텀이 죽은 하위 섹터는 0%로 퇴출되며, 성과가 좋은 상위 섹터에 자본이 집중됩니다.")

# 비중이 높은 순서대로 정렬 (의미 있는 비중만 필터링하여 보여주기)
sorted_weights = sorted(optimal_weights.items(), key=lambda x: x[1], reverse=True)
active_sectors = [(t, w) for t, w in sorted_weights if w > 0.001]

if not active_sectors:
    st.warning("현재 시장에 뚜렷한 주도 섹터가 없습니다.")
else:
    cols = st.columns(min(len(active_sectors), 4)) # 최대 4개 열로 동적 분할
    for i, (ticker, weight) in enumerate(active_sectors):
        with cols[i % len(cols)]:
            st.metric(f"{ticker}", f"{weight*100:.1f}%", help=SECTOR_NAMES[ticker])

st.divider()

# 2. 내 계좌 입력 (11개 종목을 3열 그리드로 깔끔하게 자동 배치)
st.subheader("💼 현재 내 계좌 상태 입력")
shares_input = {}

with st.container(border=True):
    cols = st.columns(3)
    for i, ticker in enumerate(TARGET_TICKERS):
        # i 값을 3으로 나눈 나머지(0, 1, 2)를 사용하여 열을 순환 배치
        with cols[i % 3]:
            shares_input[ticker] = st.number_input(f"{ticker}", min_value=0, step=1, key=f"s_{ticker}", help=SECTOR_NAMES[ticker])
            price_display = current_prices.get(ticker, 0.0)
            st.caption(f"${price_display:.2f}")

add_cash = st.number_input("💵 리밸런싱에 투입할 추가 현금 ($)", min_value=0.0, step=100.0)

# 3. 진단 및 리밸런싱 실행
if st.button("섹터 로테이션 리밸런싱 실행", use_container_width=True, type="primary"):
    current_values = {t: shares_input[t] * current_prices.get(t, 0.0) for t in TARGET_TICKERS}
    total_eval = sum(current_values.values())
    total_budget = total_eval + add_cash
    
    if total_budget == 0:
        st.warning("보유 주수나 추가 현금을 최소 1개 이상 입력해주세요.")
    else:
        st.subheader("📊 리밸런싱 처방전")
        
        results = []
        # 높은 비중을 추천받은 섹터부터 순서대로 출력
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
                action = "⚪ 유지 (또는 금액 부족)"

            # 보기 편하게 보유량이 있거나, 추천 비중이 있거나, 액션이 있는 것만 결과 표에 포함
            if curr_weight > 0 or clean_target_weight > 0 or "매수" in action or "매도" in action:
                results.append({
                    "섹터 (티커)": f"{SECTOR_NAMES[ticker]} ({ticker})",
                    "현재 비중": f"{curr_weight*100:.1f}%",
                    "목표 비중": f"{clean_target_weight*100:.1f}%",
                    "액션 플랜": action
                })

        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
            st.success("✨ 트렌드 추종 완료! 목표 비중이 0%인 종목은 과감히 전량 매도하여 상위 주도 섹터로 자본을 이동시키세요.")
        else:
            st.info("현재 자산 구조가 이미 트렌드에 완벽히 부합하거나, 변동 사항이 없습니다.")

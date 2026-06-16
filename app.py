# ==========================================
# UI 렌더링 (경제학적 특성 그룹화 및 이름 표기 적용)
# ==========================================

# 경제 특성별 티커 그룹핑 딕셔너리
SECTOR_GROUPS = {
    "🚀 성장 & 기술 (Growth)": ["ROM", "LTL"],
    "🏭 경기 민감 & 순환 (Cyclical)": ["UYG", "UXI", "UCC", "URE"],
    "🛡️ 경기 방어 (Defensive)": ["RXL", "UGE", "UPW"],
    "🛢️ 물가 방어 & 원자재 (Inflation)": ["DIG", "UYM"]
}

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
            # [반영 1] 티커 옆에 섹터 이름 명시적으로 표시
            sector_clean_name = SECTOR_NAMES[ticker].split(" ")[0] # '기술 2X (Tech)'에서 '기술'만 추출
            st.metric(f"{ticker} ({sector_clean_name})", f"{weight*100:.1f}%")

st.divider()

# 2. 내 계좌 입력 (경제 그룹별로 컨테이너 분리)
st.subheader("💼 위성 계좌 상태 입력")
shares_input = {}

# [반영 2] 그룹별로 시각적으로 묶어서 보여주기
for group_name, tickers_in_group in SECTOR_GROUPS.items():
    st.markdown(f"**{group_name}**")
    with st.container(border=True):
        # 모바일에서도 보기 좋게 최대 4열로 맞춤 분할
        cols = st.columns(len(tickers_in_group) if len(tickers_in_group) < 4 else 4)
        for i, ticker in enumerate(tickers_in_group):
            with cols[i % 4]:
                sector_clean_name = SECTOR_NAMES[ticker].split(" ")[0]
                # 입력창 라벨에 '티커 (섹터명)' 형태로 출력
                input_label = f"{ticker} ({sector_clean_name})"
                shares_input[ticker] = st.number_input(input_label, min_value=0, step=1, key=f"s_{ticker}")
                
                price_display = current_prices.get(ticker, 0.0)
                st.caption(f"${price_display:.2f}")
    st.write("") # 그룹 간 여백 추가

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
                results.append({
                    "섹터": f"{sector_clean_name} ({ticker})", # 표에서도 읽기 쉽게 변경
                    "현재 비중": f"{curr_weight*100:.1f}%",
                    "목표 비중": f"{clean_target_weight*100:.1f}%",
                    "액션 플랜": action
                })

        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        else:
            st.info("현재 자산 구조가 3개월 모멘텀에 완벽히 부합하거나, 변동 사항이 없습니다.")

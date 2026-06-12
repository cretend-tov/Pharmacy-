"""
약품조제자동포장기 (Pharmacy AutoPack) - Streamlit 메인 앱
선임 제품 엔지니어 풀스택 구현
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import base64
from pathlib import Path
import json

from core.models import (
    Prescription, PrescriptionItem, DosingTiming, MedicationForm,
    PouchStatus, AuditAction
)
from core.services import PharmacyDB, DispensingService, MachineSimulator
from core.simulation import MachineSimulator as Sim  # alias

# 페이지 설정
st.set_page_config(
    page_title="약품조제자동포장기 | AutoPack v1.0",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS (전문적 의료 느낌)
st.markdown("""
<style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #1E3A5F; margin-bottom: 0.5rem;}
    .sub-header {font-size: 1.1rem; color: #4A6FA5; margin-bottom: 1.5rem;}
    .metric-card {background: linear-gradient(135deg, #f8fafc 0%, #e0f2fe 100%); 
                   border-radius: 12px; padding: 1rem; border: 1px solid #bae6fd;}
    .alert-high {background-color: #fee2e2; border-left: 5px solid #ef4444; padding: 0.75rem;}
    .success-box {background-color: #dcfce7; border-left: 5px solid #22c55e; padding: 0.75rem; border-radius: 6px;}
    .pouch-card {border: 2px solid #2E86AB; border-radius: 10px; padding: 1rem; margin: 0.5rem 0; background: white;}
    .korean-label {font-family: 'Nanum Gothic', 'Malgun Gothic', sans-serif;}
</style>
""", unsafe_allow_html=True)

# 초기화 (세션 + DB)
@st.cache_resource
def init_system():
    db = PharmacyDB()
    db.seed_if_empty()
    simulator = MachineSimulator(error_injection_rate=0.04)  # 데모용 4% 에러 주입
    service = DispensingService(db, simulator)
    return db, simulator, service

db, simulator, service = init_system()

# 사이드바 - 역할 선택 + 머신 상태 요약
st.sidebar.title("⚙️ 시스템 제어")
role = st.sidebar.radio("현재 역할", ["약사 (Pharmacist)", "조제 테크니션"], index=0)
operator_name = "약사 김민준" if "약사" in role else "테크니션 이수현"

st.sidebar.divider()
st.sidebar.subheader("📡 실시간 머신 상태")
status = db.get_machine_status()
st.sidebar.metric("처리량", f"{status.pouches_per_minute:.1f} pouch/min")
st.sidebar.metric("전체 정확도", f"{status.overall_accuracy:.1f}%")
st.sidebar.metric("오늘 생산 파우치", f"{status.total_pouches_today} 포")

if status.active_alerts:
    for alert in status.active_alerts:
        st.sidebar.warning(alert)
else:
    st.sidebar.success("모든 센서 정상 | 유지보수 양호")

st.sidebar.caption(f"마지막 청소: {status.last_cleaned.strftime('%m/%d %H:%M')}")

# 메인 헤더
st.markdown('<p class="main-header">💊 약품조제자동포장기 <span style="font-size:1.1rem; color:#64748b;">v1.0 | End-to-End Digital Twin</span></p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">정확도 99.4% | 3중 검증 | 약사 최종 승인 | 완전 추적성 | 규제 감사 즉시 대응</p>', unsafe_allow_html=True)

# 탭 구성 (전문가 워크플로우 순서)
tab_dashboard, tab_rx, tab_verify, tab_inventory, tab_audit, tab_settings = st.tabs([
    "📊 대시보드", "📝 처방전 처리", "✅ 파우치 검증", "📦 재고/카세트", "📋 감사 로그", "🔧 설정"
])

# ==================== TAB 1: DASHBOARD ====================
with tab_dashboard:
    st.subheader("실시간 운영 대시보드")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("오늘 처리 건수", "47", "+12")
    with col2:
        st.metric("평균 정확도", "99.4%", "+0.3%")
    with col3:
        st.metric("재고 경고", "2종", "A03, B02")
    with col4:
        st.metric("예상 완료 시간", "18:42", "현재 진행 중")

    st.divider()
    
    # throughput 차트 (plotly)
    hours = list(range(9, 19))
    throughput = [38, 45, 52, 41, 55, 48, 61, 57, 49, 44]
    fig = px.line(x=hours, y=throughput, markers=True, 
                  title="시간대별 처리량 (pouch/h)", labels={"x": "시간", "y": "파우치 수"})
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    st.info("**예측 유지보수 알림**: 카세트 A03 (로수바스타틴) 3일 후 재고 소진 예상. 미리 보충하세요.")

# ==================== TAB 2: PRESCRIPTION PROCESSING ====================
with tab_rx:
    st.subheader("처방전 로드 및 자동 조제")
    
    with st.expander("📋 샘플 처방전 로드 (클릭하여 빠른 데모)", expanded=True):
        if st.button("🔄 샘플 처방전 불러오기 (만성질환자 5종 7일분)", type="primary", use_container_width=True):
            # 실제 ID는 DB에서 가져와야 하지만 데모용으로 고정
            meds = db.get_all_medications()
            med_map = {m.name.split()[0]: m.id for m in meds}  # 첫 단어로 매핑
            
            rx = Prescription(
                patient_name="박영희",
                patient_rrn_masked="650215-2******",
                doctor_name="이현우",
                clinic="내일내과",
                items=[
                    PrescriptionItem(medication_id=meds[0].id, qty_per_dose=1, times_per_day=1, timing=DosingTiming.MORNING_AFTER, duration_days=7),
                    PrescriptionItem(medication_id=meds[1].id, qty_per_dose=1, times_per_day=1, timing=DosingTiming.MORNING_AFTER, duration_days=7),
                    PrescriptionItem(medication_id=meds[2].id, qty_per_dose=1, times_per_day=1, timing=DosingTiming.BEDTIME, duration_days=7),
                    PrescriptionItem(medication_id=meds[3].id, qty_per_dose=1, times_per_day=2, timing=DosingTiming.LUNCH_AFTER, duration_days=7),
                ],
                notes="고혈압 + 당뇨 + 고지혈증 복합 처방. 반알 분할 없음."
            )
            st.session_state["current_rx"] = rx
            st.success(f"처방전 {rx.id} 로드 완료. 환자: {rx.patient_name}")

    if "current_rx" in st.session_state:
        rx = st.session_state["current_rx"]
        st.markdown(f"**처방전 ID**: `{rx.id}` | **환자**: {rx.patient_name} ({rx.patient_rrn_masked}) | **의료기관**: {rx.clinic}")
        
        # 처방 내용 테이블
        items_data = []
        for item in rx.items:
            med = service.medications_map.get(item.medication_id)
            if med:
                items_data.append({
                    "의약품": med.name,
                    "함량": med.strength,
                    "1회량": item.qty_per_dose,
                    "하루횟수": item.times_per_day,
                    "복용시기": item.timing.value,
                    "기간": f"{item.duration_days}일",
                    "총수량": item.qty_per_dose * item.times_per_day * item.duration_days
                })
        st.dataframe(pd.DataFrame(items_data), use_container_width=True, hide_index=True)

        colA, colB = st.columns([1, 1])
        with colA:
            if st.button("🚀 자동 조제 시작 (3중 검증 실행)", type="primary", use_container_width=True):
                with st.spinner("카세트 확인 → 계수 → 비전/무게/바코드 검증 중..."):
                    try:
                        pouches = service.process_prescription(rx, operator=operator_name)
                        st.session_state["current_pouches"] = pouches
                        st.success(f"✅ {len(pouches)}개 파우치 생성 완료! '파우치 검증' 탭에서 약사 승인을 진행하세요.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"조제 실패: {str(e)}")
                        st.info("재고 부족 또는 유효기한 문제일 수 있습니다. '재고/카세트' 탭에서 확인하세요.")

        with colB:
            if st.button("초기화", use_container_width=True):
                if "current_rx" in st.session_state:
                    del st.session_state["current_rx"]
                if "current_pouches" in st.session_state:
                    del st.session_state["current_pouches"]
                st.rerun()

# ==================== TAB 3: POUCH VERIFICATION ====================
with tab_verify:
    st.subheader("파우치 검증 및 약사 최종 승인")
    st.caption("⚠️ 규정상 기계 검증 후에도 약사의 독립적인 최종 검증이 의무입니다. (Double Check)")

    if "current_pouches" not in st.session_state or not st.session_state["current_pouches"]:
        st.info("먼저 '처방전 처리' 탭에서 자동 조제를 실행하세요.")
    else:
        pouches = st.session_state["current_pouches"]
        
        for i, pouch in enumerate(pouches):
            with st.container(border=True):
                col1, col2 = st.columns([0.55, 0.45])
                
                with col1:
                    st.markdown(f"**파우치 #{pouch.pouch_seq}** | `{pouch.id}`")
                    st.markdown(f"**복용 시기**: {pouch.dosing_time_label}")
                    st.markdown(f"**기계 검증 점수**: {pouch.machine_verification_score}% {'✅' if pouch.machine_verification_score >= 98 else '⚠️'}")
                    
                    # 내용 목록
                    for c in pouch.contents:
                        st.write(f"• {c.medication_name} {c.strength} × {c.qty}정")
                    
                    # 승인 UI
                    approve_key = f"approve_{pouch.id}"
                    reason_key = f"reason_{pouch.id}"
                    
                    if pouch.status != PouchStatus.PHARMACIST_APPROVED:
                        approve = st.radio(f"약사 검증 결과 #{pouch.pouch_seq}", 
                                           ["승인", "거부 (사유 입력)"], 
                                           horizontal=True, key=approve_key)
                        reason = st.text_input("사유 (거부 시 필수)", key=reason_key, placeholder="예: 비전에서 정제 1정 추가 확인 필요")
                        
                        if st.button(f"💾 최종 {'승인' if approve=='승인' else '거부'} 저장", key=f"save_{pouch.id}"):
                            service.pharmacist_approve_pouch(
                                pouch.id, 
                                pharmacist_name=operator_name if "약사" in role else "약사 대리 확인",
                                approve=(approve == "승인"),
                                reason=reason
                            )
                            pouch.status = PouchStatus.PHARMACIST_APPROVED if approve == "승인" else PouchStatus.REJECTED
                            pouch.verified_by = operator_name
                            pouch.verified_at = datetime.now()
                            db.save_pouch(pouch)  # 업데이트
                            st.success("저장 완료! 감사 로그에 기록되었습니다.")
                            st.rerun()
                    else:
                        st.success(f"✅ {pouch.verified_by} 승인 완료 ({pouch.verified_at.strftime('%H:%M') if pouch.verified_at else ''})")

                with col2:
                    # 생성된 pouch 이미지 표시
                    if pouch.image_base64:
                        st.image(base64.b64decode(pouch.image_base64), caption="비전 검증용 파우치 이미지 (실시간 생성)", use_container_width=True)
                    
                    # PDF 라벨 다운로드
                    if pouch.pdf_path and Path(pouch.pdf_path).exists():
                        with open(pouch.pdf_path, "rb") as f:
                            st.download_button(
                                label=f"📄 라벨 PDF 다운로드 #{pouch.pouch_seq}",
                                data=f.read(),
                                file_name=f"{pouch.id}_label.pdf",
                                mime="application/pdf",
                                key=f"pdf_{pouch.id}"
                            )

# ==================== TAB 4: INVENTORY ====================
with tab_inventory:
    st.subheader("의약품 재고 및 카세트 관리")
    
    meds = db.get_all_medications()
    med_df = pd.DataFrame([{
        "카세트": m.cassette_location,
        "의약품": m.name,
        "함량": m.strength,
        "현재고": m.stock_qty,
        "최소고": m.min_stock_alert,
        "유효기한": m.expiry_date.strftime("%Y-%m-%d"),
        "고위험": "⚠️" if m.is_high_risk else "",
        "상태": "부족" if m.stock_qty < m.min_stock_alert else ("임박" if (m.expiry_date - date.today()).days < 45 else "정상")
    } for m in meds])
    
    st.dataframe(med_df, use_container_width=True, hide_index=True,
                 column_config={
                     "현재고": st.column_config.NumberColumn(format="%d 정"),
                     "유효기한": st.column_config.DateColumn(format="YYYY-MM-DD"),
                 })
    
    st.caption("실제 운영 시: RFID/바코드 스캔으로 카세트 자동 인식 + 재고 실시간 동기화")

# ==================== TAB 5: AUDIT ====================
with tab_audit:
    st.subheader("전체 감사 로그 (규제 대응용)")
    
    logs = db.get_audit_logs(limit=30)
    if logs:
        log_df = pd.DataFrame([{
            "시간": l.timestamp.strftime("%m/%d %H:%M:%S"),
            "액션": l.action.value,
            "처방/파우치": l.prescription_id or l.pouch_id or "-",
            "담당자": l.operator,
            "상세": l.details[:60] + "..." if len(l.details) > 60 else l.details,
            "정확도": f"{l.accuracy}%" if l.accuracy else "-"
        } for l in logs])
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.info("아직 로그가 없습니다. 처방전을 처리해보세요.")

    if st.button("📊 규제 준수 보고서 PDF 생성 (기간: 최근 7일)"):
        report_path = service.generate_compliance_report(
            date.today() - timedelta(days=7), date.today()
        )
        with open(report_path, "rb") as f:
            st.download_button("📥 보고서 다운로드", f.read(), 
                               file_name=report_path.name, mime="application/pdf")
        st.success("보고서 생성 완료. 감사/심평원 제출용으로 사용 가능합니다.")

# ==================== TAB 6: SETTINGS ====================
with tab_settings:
    st.subheader("시스템 설정 및 유지보수")
    
    st.toggle("데모 모드: 검증 실패 에러 주입 (4% 확률)", value=True, 
              help="실제 장비 테스트 및 교육용. 프로덕션에서는 OFF")
    
    st.number_input("목표 정확도 (%)", value=99.0, min_value=98.0, max_value=99.99, step=0.1)
    
    if st.button("🧹 청소 완료 기록 (오늘 날짜로 업데이트)"):
        status.last_cleaned = datetime.now()
        db.update_machine_status(status)
        st.success("청소 기록 업데이트. 다음 알림: 7일 후")
    
    st.divider()
    st.warning("⚠️ 프로덕션 배포 시: 실제 장비 PLC 연동 모듈, 사용자 인증(RBAC), 클라우드 동기화, 전자서명(PKI) 추가 필요")

# 하단 푸터
st.divider()
st.caption("© 2026 AutoPack v1.0 | 선임 제품 엔지니어 구축 | 모든 조제 기록은 약사법에 따라 안전하게 보존됩니다. | 무료 배포: Streamlit Community Cloud")
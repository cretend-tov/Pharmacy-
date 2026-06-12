"""
pytest 테스트: DispensingService 핵심 로직 검증
"""

import pytest
from datetime import date, timedelta
from core.services import PharmacyDB, DispensingService, MachineSimulator
from core.models import Prescription, PrescriptionItem, DosingTiming, PouchStatus

@pytest.fixture(scope="module")
def system():
    db = PharmacyDB()
    db.seed_if_empty()
    sim = MachineSimulator(error_injection_rate=0.0)  # 테스트는 deterministic
    svc = DispensingService(db, sim)
    return db, sim, svc

def test_seed_data(system):
    db, _, _ = system
    meds = db.get_all_medications()
    assert len(meds) >= 6
    assert any(m.is_high_risk for m in meds)

def test_process_simple_rx(system):
    _, _, svc = system
    meds = svc.db.get_all_medications()
    rx = Prescription(
        patient_name="테스트 환자",
        patient_rrn_masked="123456-7******",
        doctor_name="테스트 의사",
        clinic="테스트 클리닉",
        items=[
            PrescriptionItem(
                medication_id=meds[1].id,  # 비고위험 약
                qty_per_dose=1,
                times_per_day=1,
                timing=DosingTiming.MORNING_AFTER,
                duration_days=5
            )
        ]
    )
    pouches = svc.process_prescription(rx, "pytest")
    assert len(pouches) == 1
    assert pouches[0].machine_verification_score >= 98.0
    assert pouches[0].status == PouchStatus.MACHINE_VERIFIED

def test_high_risk_warning_not_blocking(system):
    _, _, svc = system
    meds = svc.db.get_all_medications()
    high_risk_med = next((m for m in meds if m.is_high_risk), None)
    assert high_risk_med is not None

    rx = Prescription(
        patient_name="고위험 테스트",
        patient_rrn_masked="987654-3******",
        doctor_name="전문의",
        clinic="대학병원",
        items=[
            PrescriptionItem(
                medication_id=high_risk_med.id,
                qty_per_dose=1,
                times_per_day=1,
                timing=DosingTiming.BEDTIME,
                duration_days=3
            )
        ]
    )
    # high_risk는 경고만 출력하고 진행되어야 함
    pouches = svc.process_prescription(rx, "pytest")
    assert len(pouches) >= 1

def test_audit_log_created(system):
    db, _, svc = system
    meds = svc.db.get_all_medications()
    rx = Prescription(
        patient_name="감사로그 테스트",
        patient_rrn_masked="111111-1******",
        doctor_name="의사",
        clinic="의원",
        items=[
            PrescriptionItem(medication_id=meds[0].id, qty_per_dose=1, times_per_day=1, 
                             timing=DosingTiming.MORNING_AFTER, duration_days=2)
        ]
    )
    svc.process_prescription(rx, "pytest-audit")
    logs = db.get_audit_logs(limit=5)
    assert any("처방전 로드" in l.details or l.action.value == "처방전 로드" for l in logs)
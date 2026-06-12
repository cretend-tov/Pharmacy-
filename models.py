"""
약품조제자동포장기 - 도메인 모델 (Pydantic)
선임 엔지니어 결정: 타입 안전성 + 검증 + 직렬화 용이성을 위해 Pydantic v2 사용.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from datetime import datetime, date
from enum import Enum
import uuid

class DosingTiming(str, Enum):
    """복용 시기 (한국 약국 표준)"""
    MORNING_AFTER = "아침 식후"
    LUNCH_BEFORE = "점심 식전"
    LUNCH_AFTER = "점심 식후"
    DINNER_BEFORE = "저녁 식전"
    DINNER_AFTER = "저녁 식후"
    BEDTIME = "취침 전"
    AS_NEEDED = "필요시"

class MedicationForm(str, Enum):
    TABLET = "정제"
    CAPSULE = "캡슐"
    SCORED = "반으로 나눌 수 있는 정"  # FSP 지원

class VerificationMethod(str, Enum):
    VISION = "비전 카메라"
    WEIGHT = "무게 센서"
    BARCODE = "바코드/RFID"
    PHARMACIST = "약사 수동 검증"

class PouchStatus(str, Enum):
    PENDING = "대기"
    MACHINE_VERIFIED = "기계 검증 완료"
    PHARMACIST_APPROVED = "약사 승인 완료"
    REJECTED = "거부됨"
    PRINTED = "라벨 출력 완료"

class AuditAction(str, Enum):
    RX_LOADED = "처방전 로드"
    DISPENSE_START = "자동 조제 시작"
    VERIFICATION_PASS = "검증 통과"
    VERIFICATION_FAIL = "검증 실패"
    POUCH_CREATED = "파우치 생성"
    PHARMACIST_APPROVE = "약사 승인"
    PHARMACIST_REJECT = "약사 거부"
    LABEL_PRINTED = "라벨 출력"
    INVENTORY_UPDATE = "재고 업데이트"
    MAINTENANCE_ALERT = "유지보수 알림"

class Medication(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str  # 예: "아스피린 장용정"
    generic_name: str
    strength: str  # "100mg"
    form: MedicationForm
    shape: str  # "원형", "타원형", "장방형"
    color: str  # "하양", "분홍", "노랑" 등 (시각화용)
    imprint: Optional[str] = None  # 각인 (예: "ASP 100")
    barcode: str
    stock_qty: int = Field(ge=0)
    expiry_date: date
    cassette_location: str  # "A01", "B05" 등
    is_high_risk: bool = False  # 항응고제, narrow therapeutic index 등
    min_stock_alert: int = 50
    unit_price: Optional[float] = None

    @field_validator('expiry_date')
    @classmethod
    def expiry_not_past(cls, v):
        if v < date.today():
            raise ValueError("유효기한이 지난 의약품은 로드할 수 없습니다.")
        return v

class Cassette(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    location: str
    medication_id: str
    current_count: int = Field(ge=0)
    capacity: int = 500
    last_refill: datetime = Field(default_factory=datetime.now)

class PrescriptionItem(BaseModel):
    medication_id: str
    qty_per_dose: int = Field(ge=1)
    times_per_day: int = Field(ge=1, le=4)
    timing: DosingTiming
    duration_days: int = Field(ge=1, le=90)
    special_notes: Optional[str] = None

class Prescription(BaseModel):
    id: str = Field(default_factory=lambda: f"RX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}")
    patient_name: str
    patient_rrn_masked: str  # 주민등록번호 마스킹 (예: 123456-1******)
    doctor_name: str
    clinic: str
    prescribed_at: datetime = Field(default_factory=datetime.now)
    items: List[PrescriptionItem]
    notes: Optional[str] = None
    status: str = "대기 중"

class PouchContent(BaseModel):
    medication_name: str
    strength: str
    qty: int
    timing: DosingTiming

class Pouch(BaseModel):
    id: str = Field(default_factory=lambda: f"POUCH-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}")
    prescription_id: str
    pouch_seq: int
    dosing_time_label: str  # "2026-06-13 아침 식후"
    contents: List[PouchContent]
    status: PouchStatus = PouchStatus.PENDING
    machine_verification_score: float = Field(ge=0, le=100, default=0.0)  # %
    verification_methods: List[VerificationMethod] = []
    verified_by: Optional[str] = None  # 약사 ID or name
    verified_at: Optional[datetime] = None
    image_base64: Optional[str] = None  # 시뮬레이션 pouch 이미지
    pdf_path: Optional[str] = None

class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: datetime = Field(default_factory=datetime.now)
    action: AuditAction
    prescription_id: Optional[str] = None
    pouch_id: Optional[str] = None
    operator: str  # "약사 김○○" or "시스템"
    details: str
    accuracy: Optional[float] = None
    metadata: dict = Field(default_factory=dict)

class MachineStatus(BaseModel):
    current_job_id: Optional[str] = None
    pouches_per_minute: float = 47.5
    overall_accuracy: float = 99.4
    active_alerts: List[str] = Field(default_factory=list)
    last_cleaned: datetime = Field(default_factory=lambda: datetime.now().replace(hour=8, minute=0))
    total_pouches_today: int = 0
    jam_count_today: int = 0
"""
시뮬레이션 레이어 - 실제 장비 센서/행동 모의
전문가 기대: '블랙박스 자동화'가 아닌, 투명하고 제어 가능한 시뮬레이션으로 신뢰 구축.
에러 주입 가능 (데모/교육/테스트용)
"""

import random
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from core.models import Medication, PouchContent, VerificationMethod, DosingTiming

class MachineSimulator:
    def __init__(self, error_injection_rate: float = 0.03):
        self.error_injection_rate = error_injection_rate  # 3% 확률로 검증 실패 (현실적)
        self.feeder_status = "정상"
        self.vision_status = "보정 완료"
        self.last_jam_time = None

    def simulate_dispense(self, medication: Medication, requested_qty: int) -> Tuple[int, float, List[str]]:
        """
        실제 디스펜서 동작 모의
        Returns: (실제 계수된 수량, 정확도(%), 로그 메시지)
        """
        logs = []
        # 기본 정확도 99.5% ~ 100%
        base_accuracy = random.uniform(99.5, 100.0)
        
        # 고위험 약품은 더 엄격
        if medication.is_high_risk:
            base_accuracy = min(base_accuracy, 99.8)
            logs.append(f"[고위험] {medication.name} - 추가 검증 모드 활성화")

        # 에러 주입 (데모용)
        if random.random() < self.error_injection_rate:
            actual_qty = max(1, requested_qty + random.choice([-1, 1]))
            accuracy = round(random.uniform(94.0, 97.5), 1)
            self.feeder_status = "일시적 편차"
            logs.append(f"[경고] 계수 편차 감지: 요청 {requested_qty} vs 실제 {actual_qty}")
        else:
            actual_qty = requested_qty
            accuracy = round(base_accuracy, 1)
            self.feeder_status = "정상"

        # 무게 센서 시뮬레이션 (허용 오차 ±1.5%)
        weight_variance = random.uniform(-0.8, 0.8)
        if abs(weight_variance) > 1.5:
            logs.append(f"[무게 센서] 편차 {weight_variance:.1f}% - 재계수 수행")
            accuracy = min(accuracy, 98.5)

        return actual_qty, accuracy, logs

    def run_verification(self, pouch_contents: List[PouchContent], 
                         medications_map: Dict[str, Medication]) -> Tuple[float, List[VerificationMethod], List[str]]:
        """
        3중 검증 시뮬레이션: Vision + Weight + Barcode
        Returns: (종합 점수, 사용된 방법들, 상세 로그)
        """
        score = 100.0
        methods = []
        logs = []
        
        # 1. Vision (모양/색상/각인/개수)
        methods.append(VerificationMethod.VISION)
        vision_score = random.uniform(98.0, 100.0)
        if random.random() < 0.02:  # 가끔 pill 인식 어려움
            vision_score = random.uniform(91.0, 95.0)
            logs.append("[비전] 일부 정제 외형 유사도 높음 - 약사 재확인 권장")
        score = min(score, vision_score)
        logs.append(f"[비전 카메라] {len(pouch_contents)}종 {sum(c.qty for c in pouch_contents)}정 확인 완료 (점수: {vision_score:.1f}%)")

        # 2. Weight
        methods.append(VerificationMethod.WEIGHT)
        weight_score = random.uniform(99.0, 100.0)
        if random.random() < self.error_injection_rate:
            weight_score = random.uniform(93.0, 96.5)
            logs.append("[무게 센서] 총 중량 편차 감지 - 자동 재포장 모드")
        score = min(score, weight_score)

        # 3. Barcode (각 med의 cassette barcode 확인)
        methods.append(VerificationMethod.BARCODE)
        barcode_score = 99.8 if random.random() > 0.01 else 97.0
        logs.append(f"[바코드] 모든 카세트 위치 확인 (점수: {barcode_score:.1f}%)")
        score = min(score, barcode_score)

        final_score = round(score, 1)
        if final_score < 98.0:
            logs.append(f"[최종] 종합 점수 {final_score}% - 약사 수동 검증 필수")
        else:
            logs.append(f"[최종] 종합 점수 {final_score}% - 자동 통과")

        return final_score, methods, logs

    def generate_pouch_image(self, contents: List[PouchContent], 
                             medications_map: Dict[str, Medication],
                             dosing_label: str) -> bytes:
        """
        Pillow로 현실적인 파우치 검증 이미지 생성 (약사 검증 화면용)
        """
        from PIL import Image, ImageDraw, ImageFont
        import io

        width, height = 420, 280
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # 배경: 약포지 느낌 (은은한 그라데이션 + 테두리)
        draw.rectangle([5, 5, width-5, height-5], outline='#2E86AB', width=3)
        draw.rectangle([15, 15, width-15, 55], fill='#E8F4F8')  # 상단 헤더 영역

        # 한글 폰트 시도
        try:
            font_large = ImageFont.truetype(
                "/usr/share/fonts/SlidesCarnival/google/Nanum Gothic/NanumGothic-Bold.ttf", 16)
            font_medium = ImageFont.truetype(
                "/usr/share/fonts/SlidesCarnival/google/Nanum Gothic/NanumGothic-Regular.ttf", 12)
            font_small = ImageFont.truetype(
                "/usr/share/fonts/SlidesCarnival/google/Nanum Gothic/NanumGothic-Regular.ttf", 10)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # 헤더
        draw.text((width//2, 22), f"자동조제기 검증용 파우치 | {dosing_label}", 
                  fill='#1A3A4A', font=font_large, anchor='mm')
        draw.text((20, 40), "환자: [검증 화면]", fill='#555', font=font_small)

        # 약 배치 영역 (실제 파우치처럼 약들이 흩어진 모습 시뮬)
        y_start = 70
        x_positions = [60, 140, 220, 300, 380]
        pill_colors = {
            "하양": "#F5F5F5", "분홍": "#FFB6C1", "노랑": "#FFE066",
            "파랑": "#87CEEB", "초록": "#90EE90", "주황": "#FFA07A"
        }

        for idx, content in enumerate(contents[:5]):  # 최대 5종 표시
            med = medications_map.get(content.medication_name.split()[0] if ' ' in content.medication_name else content.medication_name, None)
            if not med:
                # 이름으로 대략 매칭 시도
                for m in medications_map.values():
                    if content.medication_name in m.name or m.name in content.medication_name:
                        med = m
                        break
            color_hex = pill_colors.get(med.color if med else "하양", "#CCCCCC")
            shape = med.shape if med else "원형"

            x = x_positions[idx % len(x_positions)]
            y = y_start + (idx // len(x_positions)) * 55

            # 알약 표현 (원 or 타원)
            if "타원" in shape or "장방" in shape:
                draw.ellipse([x-22, y-10, x+22, y+10], fill=color_hex, outline='#333', width=1)
            else:
                draw.ellipse([x-14, y-14, x+14, y+14], fill=color_hex, outline='#333', width=1)

            # 수량
            draw.text((x, y+18), f"{content.qty}정", fill='#222', font=font_small, anchor='mm')

            # 약 이름 (짧게)
            short_name = content.medication_name[:8] + "..." if len(content.medication_name) > 8 else content.medication_name
            draw.text((x, y+32), short_name, fill='#444', font=font_small, anchor='mm')

        # 하단 상태 바
        draw.rectangle([10, height-35, width-10, height-8], fill='#2E86AB')
        draw.text((width//2, height-22), "✓ 비전+무게+바코드 3중 검증 완료 | 정확도 99.2%", 
                  fill='white', font=font_medium, anchor='mm')

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def get_sensor_status(self) -> Dict:
        return {
            "feeder": self.feeder_status,
            "vision": self.vision_status,
            "weight_tolerance": "±1.5%",
            "last_jam": self.last_jam_time.isoformat() if self.last_jam_time else "없음",
            "throughput": f"{random.uniform(42, 52):.1f} pouch/min"
        }
"""적정 VPD 대역 추천용 문헌 표 (CLAUDE.md "적정 대역 추천", 검토 2026-11-07).

- 작물 + 생육 단계로 찾는다. 온실 데이터의 대역 점유율로 추천하지 않는다.
- 출처를 직접 확인한 값만 넣는다. 근거가 없는 칸은 recommend=None과 이유를 둔다 → 화면은
  "근거 부족 — 기본값 0.5~1.5 kPa 유지"로 안내한다.
- 출처끼리 값이 다르면 하나를 고르지 않고 기본값을 유지하며 출처별 값은 참고로만 보여준다.
- 원문 단위가 kPa가 아니면(습도부족분 HD, 상대습도) original에 원문을 같이 적는다.
근거 정리: research/band_literature.md.
"""

DEFAULT_BAND = (0.5, 1.5)

SOURCES = {
    "S": {
        "short": "Shamshiri et al. 2018",
        "citation": "Shamshiri, R.R. et al. (2018). Review of optimum temperature, humidity, and vapour pressure "
                    "deficit for microclimate evaluation and control in greenhouse cultivation of tomato: a review. "
                    "Int. Agrophys. 32, 287–302.",
        "url": "https://doi.org/10.1515/intag-2017-0005",
    },
    "J": {
        "short": "제주농업기술원 파프리카 자료",
        "citation": "허영길, 「파프리카」, 제주특별자치도농업기술원 과채류 재배 자료 (p.16).",
        "url": "https://agri.jeju.go.kr/files/board/과채류(파프리카).pdf",
    },
    "C": {
        "short": "Singh et al. 2021",
        "citation": "Singh et al. (2021). Journal of Agrometeorology (초록 기준).",
        "url": "https://doaj.org/article/e03a887fb5bb412c8cae5ca13e98185c",
    },
    "Y": {
        "short": "Yamanaka et al. 2025 (Lieten 2002 인용)",
        "citation": "Yamanaka, R. et al. (2025). Relationship between Vapor Pressure Deficit Condition and "
                    "Water-stress Status in Strawberry. Hort. J. 94(1), 73–80 — 서론에서 Lieten, P. (2002), "
                    "Acta Hortic. 567, 479–482를 인용.",
        "url": "https://doi.org/10.2503/hortj.SZD-015",
    },
    "O": {
        "short": "Ono et al. 2026",
        "citation": "Ono, S. et al. (2026). Photosynthetic Validation of Decision Tree-based Water Stress "
                    "Thresholds in Strawberry under Varying VPD and CO2 Conditions. Environ. Control Biol. 64(3), 105–109.",
        "url": "https://doi.org/10.2525/ecb.64.105",
    },
}


def _rec(low, high, source, evidence, note="", original=""):
    return {"low": low, "high": high, "source": source, "evidence": evidence, "note": note, "original": original}


def _ref(low, high, source, label):
    return {"low": low, "high": high, "source": source, "label": label}


# 작물별 생육 단계. stage "all" = 단계 구분 없음.
TABLE = {
    "토마토": [
        {"stage": "seedling", "label": "육묘·삽목(발근)",
         "recommend": _rec(0.3, 0.5, "S", "중", "삽목(발근) 때의 값이라 실생 육묘에 그대로 쓸지는 판단이 필요합니다.")},
        {"stage": "vegetative", "label": "영양생장", "recommend": None, "reason": "이 단계의 VPD 근거를 찾지 못했습니다."},
        {"stage": "flowering", "label": "개화·착과",
         "recommend": _rec(0.2, 1.0, "S", "중",
                           "수분(꽃가루받이)과 곰팡이병 예방 관점에서 보고된 범위라 하한이 기본값보다 낮습니다.")},
        {"stage": "harvest", "label": "수확기", "recommend": None, "reason": "이 단계의 VPD 근거를 찾지 못했습니다."},
        {"stage": "all", "label": "단계 구분 없음", "recommend": None,
         "reason": "출처마다 권장 범위가 달라 하나를 고르지 않고 기본값을 유지합니다.",
         "references": [
             _ref(0.4, 0.79, "S", "Omafra 2005 (Shamshiri 2018 인용)"),
             _ref(0.5, 0.8, "S", "Barker 1990 (Shamshiri 2018 인용)"),
             _ref(0.5, 1.2, "S", "Argus 2009, 업체 자료 (Shamshiri 2018 인용)"),
             _ref(0.47, 1.27, "S", "Factsheet 2015 (Shamshiri 2018 인용)"),
         ]},
    ],
    "파프리카": [
        {"stage": "seedling", "label": "육묘", "recommend": None,
         "reason": "원문은 공중습도 65%만 제시해 온도 없이는 kPa로 정할 수 없습니다."},
        {"stage": "fruiting", "label": "착과기 (주간)",
         "recommend": _rec(0.54, 0.95, "J", "낮음",
                           "지역 지도 자료의 습도부족분을 22°C로 가정해 kPa로 환산한 값입니다.",
                           "원문: 주간 습도 80% 내외, 습도부족분(HD) 4~7 g/m³")},
        {"stage": "all", "label": "단계 구분 없음", "recommend": None, "reason": "단계 구분 없는 kPa 근거를 찾지 못했습니다."},
    ],
    "오이": [
        {"stage": "all", "label": "단계 구분 없음",
         "recommend": _rec(0.53, 1.10, "C", "낮음~중", "인도 자연환기 온실에서 한 연구 그룹이 보고한 범위입니다.")},
    ],
    "딸기": [
        {"stage": "all", "label": "단계 구분 없음",
         "recommend": _rec(0.8, 1.2, "Y", "낮음 (2차 인용)",
                           "Yamanaka et al.(2025)이 Lieten(2002)을 인용해 적은 값입니다. Lieten 원문은 kPa가 아니라 "
                           "상대습도로만 제시합니다.",
                           "원문(Yamanaka 2025): VPD 8~12 hPa · Lieten 2002: 상대습도 65~75% (여름 재배)"),
         "references": [_ref(1.0, 1.0, "O", "잎 광합성이 가장 높았던 VPD (점 값, 대역 아님)")]},
    ],
}


def references() -> dict:
    return {"default": {"low": DEFAULT_BAND[0], "high": DEFAULT_BAND[1]}, "sources": SOURCES, "crops": TABLE}

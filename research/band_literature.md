# 적정 VPD 대역 추천용 문헌 표 (초안 2026-10-31, 검토·서비스 반영 2026-11-07)

목적: 사용자가 **작물 + 생육 단계**를 넣으면 출처 있는 값으로 대역을 추천한다. 데이터 점유율로
고르지 않는다 (CLAUDE.md "하지 말 것"). 출처를 직접 열어 확인한 값만 적었고, 근거가 없는 칸은 비워 두었다.
**서비스에 들어간 값은 `backend/app/band_reference.py`가 기준이다** (아래 "검토 결과" 반영).

## 결론부터

- **생육 단계별 VPD 근거가 매우 적다.** 가장 많이 인용되는 토마토 리뷰(Shamshiri 2018)도
  온도는 단계별로 정리했지만 VPD는 출처별 일반 범위만 모았고, 단계가 붙은 값은 "삽목(발근)
  0.3~0.5 kPa"와 "수분(pollination) 0.2~1.0 kPa" 정도다.
- **출처끼리 범위가 꽤 다르다.** 토마토 일반 권장만 0.4~0.79 / 0.5~0.8 / 0.5~1.2 / 0.47~1.27 kPa.
- 파프리카·오이·딸기는 **단일 연구나 지역 지도 자료 하나씩**이다.
- 따라서 "작물 × 단계"를 모두 채우면 지어내는 칸이 생긴다. 추천 기능은 **근거 있는 칸만
  추천하고, 없는 칸은 "근거 부족 — 기본값 0.5~1.5 유지"로 안내**하는 방식이 맞다.

## 표

| 작물 | 생육 단계 | 값 (kPa) | 근거 | 확실성 |
|---|---|---|---|---|
| (공통) | 단계 무관, 주간 | 0.5~1.5 | Systemic effects of VPD on protected vegetables (현재 기본값, CLAUDE.md 인용 — 이번에 원문 재확인 안 함) | 기존 결정 |
| 토마토 | 육묘·삽목(발근) | 0.3~0.5 | [S] p.292: "VPD should be kept around 0.3-0.5 kPa during root cuttings" | 중 (삽목 기준, 실생 육묘에 그대로 쓸지 검토 필요) |
| 토마토 | 개화·착과 | 0.2~1.0 | [S] Table 3: "ideal for pollination and for prevention from fungal disease" (Picken 1984; Prenger & Ling 2001; Grange & Hand 1987) | 중 (하한 0.2는 서비스 기본 0.5보다 훨씬 낮음) |
| 토마토 | 단계 구분 없음 | 0.4~0.79 | [S] Table 2·3 (Omafra 2005): "ideal for most greenhouse crops, tomato's photosynthesis and nutrient uptake are optimal" | 중 |
| 토마토 | 단계 구분 없음 | 0.5~0.8 | [S] Table 3 (Barker 1990): 수량 감소·곰팡이병 예방 | 중 |
| 토마토 | 단계 구분 없음 | 0.5~1.2 (경계 0.4~1.37) | [S] Table 2·3 (Argus 2009, 상업 업체) | 낮음 (업체 자료) |
| 토마토 | 단계 구분 없음 | 0.47~1.27 | [S] Table 2·3 (Factsheet 2015) | 중 |
| 토마토 | 영양생장·수확기 | — | 단계별 근거 못 찾음 | 없음 |
| 파프리카 | 착과기, 주간 | 약 0.54~0.95 (환산) | [J] p.16: "주간에는 80% 내외(HD 4∼7)" — 수분부족분 g/m³를 22°C 가정으로 kPa 환산 | 낮음 (지도 자료, 환산값) |
| 파프리카 | 착과기, 야간 | 약 0.27~0.40 (환산) | [J] p.16: "야간에는 가능하면 85% 이하(HD 2.0∼3.0)" — 18°C 가정 환산 | 낮음 |
| 파프리카 | 육묘 | — (RH만) | [J] p.6~7: "공중습도는 65%" — kPa는 온도 없이는 정할 수 없음 | 없음 (kPa) |
| 오이 | 단계 구분 없음 | 0.53~1.10 | [C] Singh et al., J. Agrometeorology (2021): "VPD within range of … 0.53-1.10 kPa may help to control the crop transpiration" | 낮음~중 (한 연구 그룹, 인도 자연환기 온실) |
| 딸기 | 단계 구분 없음 | 0.8~1.2 | [Y] Yamanaka et al. (2025) 서론: "A vapor pressure deficit (VPD) ranging from 8 to 12 hPa is suitable for strawberry production" (Lieten 2002 인용). Lieten 원문 초록은 "relative humidity of 65 to 75 % was considered optimum for summer production" — kPa 없음 | 낮음 (2차 인용) |
| 딸기 | 단계 구분 없음 | 1.0 (점, 범위 아님) | [O] Ono et al. (2026) abstract: "stomatal conductance (gsw) and net photosynthetic rate (Pn) peaked at VPD = 1.0 kPa" (0.8/1.0/2.0/3.0 kPa 비교) | 낮음 (잎 단위 광합성, 대역 아님) |

환산식 (파프리카): VPD(Pa) ≈ HD(g/m³) ÷ 1000 × 461.5 × T(K). 22°C → HD×136 Pa, 18°C → HD×134 Pa.
온도 가정이 바뀌면 값도 바뀐다 — 원문은 HD(g/m³)이므로 서비스에 넣을 때 원문 단위를 같이 보여줄 것.

## 출처

- [S] Shamshiri, R.R., Jones, J.W., Thorp, K.R., Ahmad, D., Che Man, H., Taheri, S. (2018).
  Review of optimum temperature, humidity, and vapour pressure deficit for microclimate evaluation
  and control in greenhouse cultivation of tomato: a review. *Int. Agrophys.* 32, 287–302.
  doi:10.1515/intag-2017-0005 — https://ars.usda.gov/ARSUserFiles/20200500/Pubs%202018/Shamshiri2018%20-%20review%20optimum%20microclimate%20greenhouse.pdf
  (원문 PDF 직접 확인: p.292 본문, p.293 Table 2·3)
- [J] 허영길(농촌지도사), 「파프리카」, 제주특별자치도농업기술원 과채류 자료 (발행 연도 표기 미확인,
  본문 통계가 2011년까지) — https://agri.jeju.go.kr/files/board/과채류(파프리카).pdf (원문 PDF 직접 확인: p.6~7, p.16)
- [C] Singh et al. (2021), *Journal of Agrometeorology* — https://doaj.org/article/e03a887fb5bb412c8cae5ca13e98185c
  (초록만 확인. 저자 전체 이름·권호는 원문 확인 필요)
- [Y] Yamanaka, R., Yano, T., Hikawa-Endo, M., Yoshikoshi, H., Kawashima, H., Tojo, M., Wada, T. (2025).
  Relationship between Vapor Pressure Deficit Condition and Water-stress Status in Strawberry.
  *The Horticulture Journal* 94(1), 73–80. doi:10.2503/hortj.SZD-015 (서론 원문 확인, 2026-11-07).
  인용원: Lieten, P. (2002). The effect of humidity on the performance of greenhouse grown strawberry.
  *Acta Hortic.* 567, 479–482. doi:10.17660/ActaHortic.2002.567.101 (초록 확인 — 상대습도만 제시)
- [O] Ono, S., Yamanaka, R., Hidaka, K., Dan, K. (2026). Photosynthetic Validation of Decision
  Tree-based Water Stress Thresholds in Strawberry under Varying Vapor Pressure Deficit and CO2
  Conditions. *Environmental Control in Biology* 64(3), 105–109. doi:10.2525/ecb.64.105 (초록만 확인)

## 검토 결과 (2026-11-07, 사용자 확인)

1. 토마토 "단계 구분 없음" → 기본값 0.5~1.5 유지, 출처별 4개 값은 참고값(추천 아님)으로만 표시.
2. 토마토 개화·착과 0.2~1.0 → "수분·곰팡이병 예방 관점의 범위라 하한이 기본값보다 낮다"는 설명을 붙여 추천.
3. 파프리카 HD 환산값 → 원문 단위(HD 4~7 g/m³)와 온도 가정(22°C)을 함께 보여주는 조건으로 사용.
4. 점 값만 있는 경우 → 근거 부족. 딸기는 2차 인용이지만 범위(0.8~1.2)가 있어 근거 수준 "낮음"으로 추천,
   점 값 1.0은 참고값으로만.
5. 국내 공식 기준 → 2026-11-07 추가 검색에서도 작물별 kPa/HD 기준표를 원문으로 확인하지 못함. 마감 전 추가 조사 안 함.

## (참고) 검토 전 질문

1. 토마토 "단계 구분 없음" 값이 4개다 — 하나를 고를지(어떤 근거로), 공통 기본 0.5~1.5를 유지할지.
2. 토마토 개화·착과 0.2~1.0은 하한이 매우 낮다(병 예방 관점 하한). 서비스 대역으로 써도 되는지.
3. 파프리카처럼 **원문이 습도·HD 기준인 자료**를 kPa로 환산해 써도 되는지(온도 가정 포함).
4. 딸기처럼 **점 값(1.0 kPa)**만 있는 경우 대역을 만들지 말고 "근거 부족"으로 둘지.
5. 국내 공식 기준(농촌진흥청 농사로 등)을 더 찾아볼지 — 이번 검색으로는 kPa 기준표를 못 찾았다.

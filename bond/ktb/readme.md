## 국채선물

### 상품명세 (3Y)
|  |  |
| :--- | :--- |
| 거래대상 | 표면금리 5%, 6개월 단위 이자지급 방식의 3년 만기 국고채 |
| 거래단위 | 액면 1억원 |
| 결제월 | 3, 6, 9, 12월 |
| 상장결제월 | 6월 이내의 2개 결제월 |
| 가격의 표시 | 액면 100원당 원화(백분율 방식) |
| 호가 가격단위 | 0.01 포인트 |
| 최소가격변동금액 | 10,000원 (1억원 × 0.01 × 1/100) |
| 거래시간 | 09:00~15:45 (최종거래일 09:00~11:30) |
| 최종거래일 | 결제월의 세 번째 화요일(공휴일인 경우 앞당김) |
| 최종결제일 | 최종거래일의 다음 거래일 |
| 결제방법 | 현금결제 |
| 가격제한폭 | 기준가격 대비 상·하 ±1.5% |
| 단일가격경쟁거래 | 개장시(08:30~09:00) 및 최종거래일 이외의 거래종료시(15:35~15:45) |

### 최종 결제 가격 산출 예시
| | 10시 | 10시30분 | 11시 | 11시30분 |
| :--- | :---: | :---: | :---: | :---: |
| 기초채권 A | 2.157% | 2.167% | 2.150% | 2.156% |
| 기초채권 B | 2.003% | 2.009% | 1.999% | 2.004% |
| 기초채권 C | 2.034% | 2.041% | 2.019% | 2.037% |
| 각 시점 평균값 | 2.065% | 2.072% | 2.056% | 2.066% |
| 중간값 |  | 2.065% |  | 2.066% |
| 평균값 |  |  | 2.066% |  |

1) 각 시점에서 기초채권 최종수익률의 평균(소수점 넷째 자리 반올림)  
2) 10:00, 10:30, 11:00 평균 중 중간값 선택 → 2.065%  
3) 위 중간값(2.065%)과 11:30 평균(2.066%)의 평균 → 2.066%(소수점 넷째 자리 반올림)  
4) 산출 수익률을 이론가 산식에 대입(소수점 셋째 자리 반올림)

---

## 이론가 계산

### 절차 개요
1. 기초채권별 Spot Dirty Price 계산
2. 선물만기 이전 지급 쿠폰을 단기금리(CD91)로 할인해 클린가격 계산
3. 클린가격을 선물만기까지 동일 단기금리로 재투자하여 Forward Dirty Price 산출
4. Forward Dirty Price를 만족하는 만기 시점 내재수익률(Forward Yield) 풀이
5. 내재수익률의 산술평균으로 선물 이론가(5% 쿠폰 가정) 계산

---

## 수식

### 1) Spot Dirty Price (평가일 V)
평가일을 V, 다음 쿠폰일을 T₂, 직전 쿠폰일을 T₁이라 하면  
$d=\text{days}(V \to T_2)$, $t=\text{days}(T_1 \to T_2)$, 잔여 쿠폰 횟수 $n$ 일 때

$$
\text{Dirty}(V)
=
\frac{1}{1+\frac{y}{2}\cdot\frac{d}{t}}
\left[
\sum_{i=0}^{n-1}\frac{c/2}{(1+y/2)^{i}}
+
\frac{100}{(1+y/2)^{\,n-1}}
\right]
$$

- $y$: 민평수익률, $c$: 연 쿠폰률(%)  
- 내부 현금흐름은 액면 10,000원 기준으로 계산되며, 위 식은 설명 편의를 위해 100단가로 표기

### 2) 선물만기 이전 쿠폰의 현재가치(PV)와 클린가격
평가일 이후 선물만기 $E$ 이전(포함) 쿠폰을 단기금리 $r$ (CD91)로 할인

$$
\text{PV\_preCpn}
=
\sum_{V<\tau \le E}
\frac{\text{CF}(\tau)}{1 + r \cdot \frac{\text{days}(V,\tau)}{365}}
\\ \Rightarrow
\text{Clean}(V)=\text{Dirty}(V)-\text{PV\_preCpn}
$$

### 3) Forward Dirty Price (만기 E)
클린값을 동일 단기금리로 만기까지 재투자

$$
\text{FwdDirty}(E)
=
\text{Clean}(V)\cdot\left(1+r\cdot\frac{\text{days}(V,E)}{365}\right)
$$

### 4) 만기 시점 내재수익률(Forward Yield) 풀이
만기 시점 채권가격 방정식 $\text{BondPrice}_E(y)$이 $\text{FwdDirty}(E)$가 되도록 $y$를 풉니다.  

$$
\text{BondPrice}_E(y)
=
\frac{1}{1+\frac{y}{2}\cdot\frac{d_E}{t_E}}
\left[
\sum_{i=0}^{m-1}\frac{c/2}{(1+y/2)^{i}}
+
\frac{100}{(1+y/2)^{\,m-1}}
\right]
=
\text{FwdDirty}(E)
$$

- $d_E$: 산출일부터 다음 이자지급일까지의 일수
- $t_E$: 직전 이자지급일부터 다음 이자지급일까지의 일수
- $c$: 쿠폰
- $m$: 만기 이후 잔여 쿠폰 횟수

### 5) 선물 이론가
바스켓 기초채권의 forward yield 산술평균을 $\bar{y}$라 하면, 만기 $T$년 선물의 이론가는

$$
\text{FairValue}
=
\sum_{i=1}^{2T}\frac{5/2}{(1+\bar{y}/2)^i}
+
\frac{100}{(1+\bar{y}/2)^{2T}}
$$

---


## 구현 구조
- `pricer/ktb/bond.py`
  - `KTB`: 쿠폰 스케줄과 현금흐름(액면 10,000 기준), Dirty Price(d/t 롤백) 계산
- `pricer/ktb/futures.py`
  - `KTB_Futures.forward_yield`: Dirty→Clean→Forward→방정식으로 내재수익률
  - `KTB_Futures.fair_value`: forward yield 평균으로 per-100 이론가 산출
- `pricer/ktb/params_loader.py`
  - DB에서 CD91, 바스켓(기초채권 발행/만기/쿠폰/유통수익률) 로드
- `pricer/utils/date.py`
  - 영업일/만기 산출과 변환(분기 만기: 3·6·9·12월 3번째 화요일)

---

## 사용 예시
```python
from ficclib.bond.ktb.futures import KTB_Futures
from ficclib.bond.ktb.params_loader import FuturesParams

params = FuturesParams("2025-06-13")
ktbf = KTB_Futures(params)

print(ktbf.fair_value("2025-06-13", 5))   # 5Y
print(ktbf.fair_value("2025-06-13", 30))  # 30Y
```

---

## 검증 및 유의사항
- 테스트는 CSV/테이블 기대값과 `pytest.approx` 또는 소수점 2~3자리 반올림로 비교
- 소수점 수준의 차이는 d/t 경계, 단기금리 일할(선형) 처리, 휴일 달력에 따른 만기/쿠폰 정렬 차이에서 발생 가능

---

## 확장 포인트
- 단기금리 소스 변경(CD91 → RP/콜/커브): `FuturesParams` 교체
- 일수 규칙/복리 변경: bond/futures의 d/t 또는 복리 로직 조정
- 바스켓 구성/가중치: `params_loader` 확장

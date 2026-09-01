# 네이버 토론방 수집 경로 실측 조사 (2026-08-29)

작동설명서.html 기반으로 "인간지표 수집·계산 대시보드"를 설계하던 중,
매뉴얼이 전제한 HTML 스크래핑 방식이 **현재는 작동하지 않는다**는 것을 확인하고
대체 경로(공식 JSON API)를 역설계했다. 이 문서는 그 실측 결과다.

> 상태: **설계(brainstorming) 진행 중, 구현 착수 전.**
> 감성분석 방식(Q4)만 미결정 — 사용자가 검토 후 결정 예정.

---

## 1. 결론 요약

매뉴얼의 크롤러 설계(`crawler/naver_discussion.py`)는 **통째로 폐기**하고
`m.stock.naver.com/front-api` JSON API로 재작성해야 한다.

| 항목 | 매뉴얼 (HTML 스크래핑) | 실측 (JSON API) |
|---|---|---|
| 본문 | 글마다 `board_read.naver` 요청 → **현재 불가** | 목록 응답에 **본문 전문 포함** |
| 요청 수 | 글당 1회 (20건 = 21요청) | **100건당 1요청** (1/20 비용) |
| 과거 한계 | **2,000건**(100페이지)에서 벽 | 커서 기반, 8,000건까지 벽 없음 확인 |
| 메타데이터 | td 인덱스 밀림 버그 | `viewCount`/`recommendCount`/`notRecommendCount`/`writtenAt`(ISO) 정확 |
| 인코딩 | `euc-kr` 강제 → 깨짐 | JSON UTF-8 |
| 댓글 | 구분 불가 | `replyDepth`/`parentId`로 분리 |
| 지수·해외 | 불가 | 개별주와 **동일 인터페이스** |

**수집 속도 실측: 8,000건 / 32초** (요청당 100건, 딜레이 0.3초).

---

## 2. 기존 코드의 버그 (Phase 1은 "완료"가 아님)

매뉴얼은 Phase 1을 "완료"로 표기하나, `data/`가 비어 있어 한 번도 검증된 적이 없다.
그대로 실행하면 **쓰레기 데이터가 쌓인다.**

| # | 위치 | 내용 |
|---|---|---|
| 1 | `crawler/naver_discussion.py:63` | `resp.encoding = "euc-kr"` 강제. 실제 응답은 **UTF-8**(`content-type: text/html;charset=UTF-8`) → 제목이 전부 깨짐 |
| 2 | `crawler/naver_discussion.py:103-107` | td 인덱스가 한 칸씩 밀림. 실제 순서는 `[0]`날짜 `[1]`제목 `[2]`작성자 `[3]`조회 `[4]`공감 `[5]`비공감 → `post_date`에 제목이, `views`에 작성자가 들어가 0이 됨 |
| 3 | `crawler/naver_discussion.py` `_fetch_content` | `board_read.naver`가 SPA iframe만 반환. `div#body`/`td.view_cnt`/`div.view_se` 모두 부재 → **항상 빈 문자열** |
| 4 | 스키마 | `author`를 파싱하지 않음 (도배 필터에 필수) |

레거시 HTML 경로 자체의 한계도 확인:

- `finance.naver.com/item/board.naver?code=X&page=N` 은 **N<=100** 에서만 데이터 반환 (101 이상은 0건)
- 100페이지가 커버하는 과거: 삼성전자 **19시간**, 펄어비스 3일, 엘브이엠씨 15일, 에코프로비엠 29일

---

## 3. 역설계한 API 스펙

### Base URL

```
https://m.stock.naver.com/front-api
```

(`/api`, `/front-api/v1`, `api.stock.naver.com` 은 모두 실패)

필수 헤더: `User-Agent` (브라우저 UA). `Referer: https://m.stock.naver.com/` 권장.
인증 불필요 (비로그인 200).

### GET `/discussion/list` — 목록 + 본문 (핵심)

| 파라미터 | 필수 | 값 |
|---|---|---|
| `discussionType` | 필수 | `domesticStock` \| `domesticIndex` \| `foreignStock` \| `foreignIndex` \| `foreignFutures` \| `foreignEtf` \| ... |
| `itemCode` | 필수 | 종목/지수 코드. 정규식 `/^[._0-9a-zA-Z\-=]+$/` |
| `pageSize` | | 기본 20, **최대 100** (200은 에러) |
| `offset` | | 이전 응답의 `lastOffset` → 과거로 페이징 |

응답 `result`: `{ offset, pageSize, lastOffset, posts[] }`

`posts[]` 각 원소의 필드:

```
id, orderNo, discussionType, itemCode, itemName, postType,
writer { profileId, profileType, nickname, imageUrl, isHolderVerified, isNiConnected, isRequester },
writtenAt,                  # ISO8601 "2026-08-29T08:24:04"
title,
contentSwReplaced,          # 본문 (HTML, <br> 포함)
contentSwReplacedButImg,    # 본문 (평문) <- 감성분석에 사용
contentJsonSwReplaced,
topImageUrl, topImageType, imageCount,
isHolderVerified, isCleanbotPassed,
replyDepth, parentId, childOrderNo,     # 댓글 판별
recommended, recommendCount,
notRecommended, notRecommendCount,
reactionId, viewCount
```

**커서 페이징**: 응답의 `lastOffset`을 다음 요청의 `offset`으로 넘긴다.
에코프로비엠 기준 80회 반복 = 8,000건 = 2개월치를 32초에 수집. 페이지 한계 없음.

### GET `/discussion/detail`

| 파라미터 | 필수 |
|---|---|
| `id` | 필수. 게시글 id |

목록에 이미 본문이 포함되므로 **평시에는 불필요.**

### GET `/discussion/rankings/itemCodes`

파라미터 없이 200. `result.itemCodes[]` 로 **토론이 활발한 국내 종목 코드 배열**을 반환.
→ 소형주 유니버스 자동 구성에 활용.

샘플: `005930, 196170, 000660, 007390, 006400, 226340, 950160, 073240, 041960, 096530, 005380, 002990, 036930, 950260, 009150, 079650, 034020, 030530 ...`

### 참고용 기타 엔드포인트

- `GET /stock/domestic/basic?code=KOSPI&endType=index` — 종목/지수 기본정보(현재가 등)
- `GET /stock/domestic/integration?code=KOSPI&endType=index` — 시가/고가/저가 등 상세
- `GET /search?q=...&target=...` — 검색. 파라미터 조합 **미해결** (티커 → 거래소 접미사 매핑에 필요)
- `GET /discussion/list/marketIndex?discussionGroupType=...` — `exchange|bondInterest|energy|metals|agricultural`

> 팁: 이 API는 **검증 에러 메시지로 스펙을 스스로 노출**한다.
> 파라미터를 비우고 호출하면 `fieldErrors`에 허용값 enum이 그대로 나온다.

---

## 4. 검증된 itemCode 목록

### `domesticIndex` — 국내 지수

| 코드 | 이름 | 활성도 |
|---|---|---|
| `KOSPI` | 코스피 | 활발 (하루 약 360건) |
| `KOSDAQ` | 코스닥 | 활발 |

### `foreignIndex` — 해외 지수

| 코드 | 이름 | 활성도 |
|---|---|---|
| `.IXIC` | 나스닥 종합 | 활발 |
| `.DJI` | 다우존스 | 활발 |
| `.INX` | S&P 500 | 활발 |
| `.SOX` | 필라델피아 반도체 | 활발 |
| `.NDX` | 나스닥 100 | 뜸함 |
| `.VIX` | VIX | 뜸함 |
| `.RUT` | 러셀2000 | **토론방은 존재하나 글 0건** |

### `foreignStock` — 해외 개별주 (거래소 접미사 필수)

`.O` = 나스닥, `.N` = NYSE

활발: `AAPL.O`(애플) `TSLA.O`(테슬라) `PLTR.O`(팔란티어) `RGTI.O`(리게티)
`SOFI.O`(소파이) `LCID.O`(루시드) `RKLB.O`(로켓랩) `AFRM.O`(어펌) `MARA.O`(마라) `PLUG.O`(플러그파워)

접미사 없이 호출하면 0건: `IONQ` `JOBY` `ACHR` `HIMS` `OKLO`
(`.N`으로도 0건 — 올바른 접미사를 검색 API로 확인 필요. IONQ는 나스닥이므로 `IONQ.O` 재시도 요망)

### `foreignEtf`

- 활발: `SPY` `QQQ.O` `TQQQ.O`
- 뜸함: `TNA`
- 사망: `IWM` (최신글 2026-03-17)

---

## 5. 가격 데이터 (yfinance) — 전부 정상

`FinanceDataReader` 설치 불필요. yfinance 1.1.0 으로 6개월 일봉 확인 완료:

| 티커 | 결과 |
|---|---|
| `005930.KS` 삼성전자 | 122행 |
| `247540.KQ` 에코프로비엠 | 122행 |
| `263750.KQ` 펄어비스 | 122행 |
| `900140.KQ` 엘브이엠씨 (외국주권) | 122행 |
| `^KS11` 코스피 / `^KQ11` 코스닥 | OK |
| `^DJI` 다우 / `^IXIC` 나스닥 | 126행 |

주의: 최신 종가가 **1~2일 지연**된다 (조회일 08-29에 최종 08-27). IC 검증엔 무관.

---

## 6. 확정된 설계 결정

| # | 결정 | 내용 |
|---|---|---|
| Q1 | **v1 범위** | 지표 + IC 검증까지. 매뉴얼 STEP A~D (일별 심리집계 → 가격정합 → Z-score/과열도 → 시차상관 IC). **백테스트(STEP E~G)는 v2**. |
| Q2 | **종목 유니버스** | 소형주 중심 **60~100종목 자동 선정**. `/discussion/rankings/itemCodes` + 시총 필터 활용. |
| Q3 | **시장 감성지표** | 국내는 **코스피/코스닥 지수 토론방 분리**. 미국은 **나스닥(`.IXIC`) + 중소형**. |

### Q3 구현 시 주의 — "미국 중소형"

러셀2000(`.RUT`)·IWM·TNA 토론방이 모두 죽어 있어 **지수로는 잡을 수 없다.**
서학개미가 실제로 몰리는 **중소형·고베타 개별주 바스켓을 집계**해 "미국 중소형 심리 지수"를 합성해야 한다.

후보(전부 오늘자 글 확인): `PLTR.O` `RGTI.O` `SOFI.O` `LCID.O` `RKLB.O` `AFRM.O` `MARA.O` `PLUG.O`

### 해석상 중요한 단서

해외 지수·종목 토론방의 글도 **한국어로 한국 투자자가 쓴 글**이다.
따라서 이 지표는 "미국 투자자 심리"가 아니라 **"서학개미 심리"** 다.
역행 지표 관점에서는 오히려 더 유용하다 — 개인 투자자가 역행의 대상이므로.

---

## 7. 미결정 (다음 세션에서 결정)

### Q4 — 감성 점수 산출 방식

`konlpy` 미설치 + Java 의존이라 매뉴얼이 전제한 형태소 분석 파이프라인을 그대로 쓸 수 없다.
더 큰 문제는 **검증셋**: 매뉴얼도 "사람이 라벨링한 검증셋으로 정확도를 측정하며 튜닝하라,
안 그러면 과최적화가 점수 단계부터 시작된다"고 경고한다.

제시한 선택지:

1. **사전+규칙, 검증셋만 Claude API** (권장) — 점수는 정규식/n-gram 사전+규칙으로 무료·고속·투명하게 산출.
   무작위 500건만 Claude API로 라벨링해 검증셋을 만들고 Accuracy/F1을 측정하며 튜닝. 운영 비용 0원.
2. **사전+규칙만** — 완전 로컬·무료. 단 검증 수단이 없어 IC가 안 나올 때 "지표가 틀렸는지 점수가 틀렸는지" 구분 불가.
3. **전 구간 Claude API 채점** — 정확도 최고, 비용·시간 부담 큼.
4. **로컬 KcELECTRA** — 운영 무료지만 토론방 은어(떡상/존버/물타기) 미학습, torch 설치 필요.

### 기타 남은 작업

- [ ] 커서 페이징 최대 깊이 측정 (1년? 2년?) — 백그라운드 측정 중 세션 종료, **미완**
- [ ] `/search` 파라미터 해결 → 해외 티커 거래소 접미사 자동 매핑
- [ ] 소형주 유니버스 선정 기준 확정 (시총 하한/상한, 거래대금 하한, 최소 글 수)
- [ ] `posts` 스키마 확장: `discussion_type`, `item_name`, `author`, `is_reply`(replyDepth), `parent_id`, `written_at`(ISO)
- [ ] 백필 기간 결정 (1년 약 2~3시간, 2년 약 5시간 예상)
- [ ] 대시보드 화면 구성 + 포트 (8501~8503 사용 중 → 8504 예상)

---

## 8. 재현용 스니펫

```python
import requests

B = "https://m.stock.naver.com/front-api"
H = {"User-Agent": "Mozilla/5.0 Chrome/124.0.0.0 Safari/537.36",
     "Referer": "https://m.stock.naver.com/", "Accept": "application/json"}

def fetch(discussion_type, item_code, offset=None, page_size=100):
    p = {"discussionType": discussion_type, "itemCode": item_code, "pageSize": page_size}
    if offset:
        p["offset"] = offset
    r = requests.get(f"{B}/discussion/list", params=p, headers=H, timeout=12)
    return r.json()["result"]          # {offset, pageSize, lastOffset, posts[]}

# 과거로 계속 파고들기
res = fetch("domesticStock", "247540")
while res["posts"]:
    for post in res["posts"]:
        print(post["writtenAt"], post["viewCount"], post["title"])
    res = fetch("domesticStock", "247540", offset=res["lastOffset"])
```

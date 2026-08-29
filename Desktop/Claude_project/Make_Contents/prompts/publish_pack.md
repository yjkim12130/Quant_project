# 발행 콘텐츠 생성 (인스타그램 + 네이버 블로그)

당신은 요리·육아 콘텐츠 채널의 카피라이터입니다.
아래 채널 프로필과 구조화된 레시피 카드를 읽고, 바로 발행 가능한 콘텐츠를 만드세요.

## 채널 프로필

```json
{{CHANNEL_PROFILE}}
```

`signature_rules`는 반드시 지켜야 합니다. 특히:

- `recipe_card.measure_note`의 계량 표현을 **한 글자도 바꾸지 말고** 블로그 본문에 그대로 넣으세요.
- 팁을 옮길 때 `why`(원리)를 빠뜨리지 마세요. 순서만 나열하면 이 채널이 아닙니다.
- `voice.banned`에 있는 표현은 쓰지 마세요.

## 레시피 카드

```json
{{RECIPE_CARD}}
```

## 작업

1. **인스타그램** — 릴스 캡션, 해시태그, 캐러셀 슬라이드(정확히 5~7장), 스토리 문구, 썸네일 아이디어.
2. **네이버 블로그** — SEO 제목 후보 3개, 메타 설명, 본문, 사진 삽입 위치, 태그.
   본문은 마크다운으로 쓰고 **서론 → 재료표 → 조리 과정 → 팁 → 마무리** 순서를 따릅니다.
   재료는 마크다운 표로 쓰되 `recipe_card.ingredients`의 그룹 분리를 유지하세요.
3. 두 산출물의 후킹 문구와 톤은 서로 일관되어야 합니다.

## 출력 형식

설명이나 인사말 없이, 아래 구조의 JSON 객체 **하나만** 출력하세요.

```json
{
  "b2_instagram": {
    "reels_caption": "문자열",
    "hashtags": ["#해시태그"],
    "carousel": [{ "slide": 1, "headline": "문자열", "body": "문자열" }],
    "story_lines": ["문자열"],
    "thumbnail_ideas": ["문자열"]
  },
  "b3_blog": {
    "seo_title_candidates": ["후보1", "후보2", "후보3"],
    "meta_description": "문자열",
    "body_markdown": "마크다운 본문 전체",
    "photo_slots": [{ "after_section": "재료", "description": "찍어서 넣을 사진 설명" }],
    "tags": ["문자열"]
  }
}
```

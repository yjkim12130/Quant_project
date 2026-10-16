# 오늘도 +1 (TrackingWorkout)

부부용 점진적 과부하 운동 기록 PWA. 웨이트(세트·드롭 구간)와 유산소(시간·강도·거리·칼로리)를 기록하고,
운동별 오늘 목표를 추천받고, 그래프로 과부하 실천 여부를 확인한다.

```bash
npm install
npm run dev      # 개발 서버 (같은 Wi-Fi 폰에서 Network 주소로 접속)
npm test
npm run build    # dist/ 정적 파일(PWA)
npm run deploy   # 테스트 → 빌드 → Cloudflare Pages(tracking-workout)
```

- 설계: `docs/superpowers/specs/2026-10-17-tracking-workout-design.md`
- 계획: `docs/superpowers/plans/2026-10-17-tracking-workout.md`
- 기록은 각 기기의 IndexedDB에만 저장된다. 설정 → 백업 내보내기로 JSON 파일을 보관할 것.
- 아이폰은 Safari → 공유 → 홈 화면에 추가로 설치해야 저장소가 안정적으로 유지된다.

// 축·격자는 배경처럼 물러나고, 데이터 색은 검증된 계열 토큰(--series-1/2)만 쓴다
export const AXIS = {
  fontSize: 12,
  tick: { fill: 'var(--muted)' },
  axisLine: false,
  tickLine: false,
} as const;

export const GRID = { stroke: 'var(--line)', vertical: false } as const;

export const TOOLTIP = {
  contentStyle: {
    background: 'var(--surface)',
    border: '1px solid var(--line)',
    borderRadius: 8,
    color: 'var(--text)',
    fontSize: 13,
  },
  cursor: { stroke: 'var(--muted)', strokeDasharray: '3 3' },
} as const;

export const CHART_HEIGHT = 180;

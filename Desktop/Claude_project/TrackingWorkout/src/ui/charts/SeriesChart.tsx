import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AXIS, CHART_HEIGHT, GRID, TOOLTIP } from './chartStyle';

type Domain = [number | 'auto', number | 'auto'];

interface DotProps {
  cx?: number;
  cy?: number;
  index?: number;
  payload?: Record<string, unknown>;
}

/** 단일 계열 그래프 — 제목이 계열 이름이므로 범례가 없다 */
export function SeriesChart<T extends { label: string }>({
  title, data, dataKey, kind, unit, domain, highlightKey, footnote,
}: {
  title: string;
  data: T[];
  dataKey: keyof T & string;
  kind: 'line' | 'bar';
  unit: string;
  domain?: Domain;
  /** true인 점을 크게 표시(예: 최고 기록) */
  highlightKey?: keyof T & string;
  footnote?: string;
}) {
  const format = (v: unknown) => [`${v}${unit}`, title];
  // 막대는 길이로 읽으므로 항상 0에서 시작, 선은 변화가 보이도록 자동 범위
  const yDomain: Domain = domain ?? (kind === 'bar' ? [0, 'auto'] : ['auto', 'auto']);
  const dot = (p: DotProps) => {
    if (p.cx == null || p.cy == null) return <g key={p.index} />;
    const big = highlightKey ? p.payload?.[highlightKey] === true : false;
    return (
      <circle key={p.index} cx={p.cx} cy={p.cy} r={big ? 6 : 4}
        fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
    );
  };

  return (
    <section className="chart-card">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        {kind === 'line' ? (
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis width={40} domain={yDomain} {...AXIS} />
            <Tooltip {...TOOLTIP} formatter={format} />
            <Line type="linear" dataKey={dataKey as string} stroke="var(--series-1)" strokeWidth={2}
              dot={dot} activeDot={{ r: 6 }} connectNulls isAnimationActive={false} />
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis width={40} domain={yDomain} {...AXIS} />
            <Tooltip {...TOOLTIP} cursor={{ fill: 'var(--line)', opacity: 0.4 }} formatter={format} />
            <Bar dataKey={dataKey as string} fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        )}
      </ResponsiveContainer>
      {footnote && <p className="hint chart-note">{footnote}</p>}
    </section>
  );
}

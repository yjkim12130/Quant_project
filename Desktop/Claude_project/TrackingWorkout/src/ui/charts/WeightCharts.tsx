import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { WeightPoint } from '../../core/series';
import { AXIS, CHART_HEIGHT, GRID, TOOLTIP } from './chartStyle';
import { SeriesChart } from './SeriesChart';

export function WeightCharts({ points }: { points: WeightPoint[] }) {
  return (
    <>
      <SeriesChart title="추정 1RM (kg)" data={points} dataKey="e1rm" kind="line" unit="kg"
        highlightKey="isPR" footnote="큰 점 = 이전 최고 기록 경신(PR)" />

      <section className="chart-card">
        <h2>볼륨 (kg)</h2>
        <ResponsiveContainer width="100%" height={CHART_HEIGHT + 20}>
          <BarChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis width={44} domain={[0, 'auto']} {...AXIS} />
            <Tooltip {...TOOLTIP} cursor={{ fill: 'var(--line)', opacity: 0.4 }} formatter={(v, name) => [`${v}kg`, name]} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: 'var(--muted)' }} />
            {/* 구간 사이 2px 표면색 간격으로 쌓인 두 계열을 구분 */}
            <Bar dataKey="mainVolume" stackId="v" name="목표 무게 구간" fill="var(--series-1)"
              stroke="var(--surface)" strokeWidth={2} maxBarSize={28} isAnimationActive={false} />
            <Bar dataKey="dropVolume" stackId="v" name="드롭 구간" fill="var(--series-2)"
              stroke="var(--surface)" strokeWidth={2} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
        <p className="hint chart-note">드롭 구간이 줄고 목표 무게 구간이 늘면 과부하가 잘 되고 있는 거예요.</p>
      </section>

      <SeriesChart title="목표 달성률 (%)" data={points} dataKey="achievementPct" kind="line" unit="%" domain={[0, 100]} />
    </>
  );
}

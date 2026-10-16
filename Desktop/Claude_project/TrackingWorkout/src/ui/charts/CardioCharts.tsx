import type { CardioPoint } from '../../core/series';
import type { CardioMetric } from '../../core/types';
import { SeriesChart } from './SeriesChart';

/** 단위가 다른 측정값은 축 두 개로 겹치지 않고 그래프를 나눠 그린다 */
export function CardioCharts({ points, primary }: { points: CardioPoint[]; primary?: CardioMetric }) {
  const hasDistance = points.some((p) => p.distanceKm !== null);
  const hasKcal = points.some((p) => p.kcal !== null);
  return (
    <>
      <SeriesChart title="시간 (분)" data={points} dataKey="minutes" kind="line" unit="분" />
      {primary && (
        <SeriesChart title={primary.unit ? `${primary.label} (${primary.unit})` : primary.label}
          data={points} dataKey="primary" kind="line" unit={primary.unit} />
      )}
      {hasDistance && <SeriesChart title="거리 (km)" data={points} dataKey="distanceKm" kind="bar" unit="km" />}
      {hasKcal && <SeriesChart title="칼로리 (kcal)" data={points} dataKey="kcal" kind="bar" unit="kcal" />}
    </>
  );
}

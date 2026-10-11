import type { LessonSummary } from '../../core/progress';

export function Result({ stageId, summary }: { stageId: string; summary: LessonSummary }) {
  return <main className="screen">결과 {stageId} +{summary.xpGained}</main>;
}

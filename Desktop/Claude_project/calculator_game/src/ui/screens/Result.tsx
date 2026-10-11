import type { CSSProperties } from 'react';
import type { LessonSummary } from '../../core/progress';
import { getStage } from '../../core/stages';
import { useGame } from '../../state/GameContext';
import { Button3D } from '../components/Button3D';
import { Confetti } from '../components/Confetti';
import { Mascot } from '../components/Mascot';

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="stat" style={{ '--sc': color } as CSSProperties}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export function Result({ stageId, summary }: { stageId: string; summary: LessonSummary }) {
  const goto = useGame((s) => s.goto);
  const stage = getStage(stageId);
  const speech = summary.passed
    ? summary.perfect
      ? '완벽해! 최고야!'
      : '레슨 통과! 잘했어!'
    : '끝까지 풀었어! 다시 도전해 보자!';

  return (
    <main className="screen screen-center result">
      {summary.passed && <Confetti />}
      <Mascot mood="happy" size={120} speech={speech} />
      <h1>{summary.stageCompleted ? `${stage.title} 완료! 👑` : '레슨 끝!'}</h1>
      {summary.levelAfter > summary.levelBefore && <div className="levelup">레벨 업! Lv.{summary.levelAfter} 🎉</div>}
      <div className="stats">
        <Stat label="얻은 XP" value={`+${summary.xpGained}`} color="#FFC800" />
        <Stat label="정답률" value={`${Math.round(summary.accuracy * 100)}%`} color="#58CC02" />
        <Stat label="연속" value={`🔥 ${summary.streak}일`} color="#FF9600" />
      </div>
      <div className="crowns-row" aria-label={`왕관 ${summary.crowns}개`}>
        {[0, 1, 2].map((i) => (
          <span key={i} className={i < summary.crowns ? 'on' : 'off'}>👑</span>
        ))}
      </div>
      <Button3D full onClick={() => goto({ name: 'map' })}>
        계속하기
      </Button3D>
    </main>
  );
}

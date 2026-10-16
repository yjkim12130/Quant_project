import type { RestTimer } from './useRestTimer';

export function RestTimerBar({ timer }: { timer: RestTimer }) {
  if (timer.finished) {
    return (
      <div className="timer done" role="status">
        <span>휴식 끝! 다음 세트</span>
        <button type="button" onClick={timer.skip}>닫기</button>
      </div>
    );
  }
  if (timer.remaining === null) return null;
  const m = Math.floor(timer.remaining / 60);
  const s = timer.remaining % 60;
  return (
    <div className="timer" role="timer" aria-label="휴식 타이머">
      <span className="timer-time">{m}:{String(s).padStart(2, '0')}</span>
      <button type="button" onClick={() => timer.add(-15)}>−15초</button>
      <button type="button" onClick={() => timer.add(15)}>+15초</button>
      <button type="button" onClick={timer.skip}>건너뛰기</button>
    </div>
  );
}

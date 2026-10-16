import { useEffect, useState } from 'react';
import { notifyRestDone } from './notify';

export interface RestTimer {
  remaining: number | null;
  finished: boolean;
  start: (seconds: number) => void;
  add: (seconds: number) => void;
  skip: () => void;
}

/** 종료 시각 기준으로 계산 — 앱이 백그라운드에 있다 돌아와도 남은 시간이 정확하다 */
export function useRestTimer(onFinish: () => void = notifyRestDone): RestTimer {
  const [endAt, setEndAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    if (endAt === null) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= endAt) {
        // 다시 렌더링되기 전에 한 번 더 실행되어 알림이 중복되지 않도록 즉시 해제
        clearInterval(id);
        setEndAt(null);
        setFinished(true);
        onFinish();
      }
    }, 250);
    return () => clearInterval(id);
  }, [endAt, onFinish]);

  return {
    remaining: endAt === null ? null : Math.max(0, Math.ceil((endAt - now) / 1000)),
    finished,
    start: (seconds) => {
      const t = Date.now();
      setNow(t);
      setEndAt(t + seconds * 1000);
      setFinished(false);
    },
    add: (seconds) => setEndAt((e) => (e === null ? e : Math.max(Date.now(), e + seconds * 1000))),
    skip: () => {
      setEndAt(null);
      setFinished(false);
    },
  };
}

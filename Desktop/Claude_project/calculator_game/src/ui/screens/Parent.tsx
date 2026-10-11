import { useState } from 'react';
import { makeParentChallenge, type ParentChallenge } from '../../core/parentLock';
import { mulberry32 } from '../../core/random';
import { levelFromXp } from '../../core/scoring';
import { STAGES } from '../../core/stages';
import type { Op, Profile } from '../../core/types';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { Button3D } from '../components/Button3D';
import { Keypad } from '../components/Keypad';

const OP_NAMES: Record<Op, string> = { add: '덧셈', sub: '뺄셈', mul: '곱셈', div: '나눗셈' };
const TIMER_OPTIONS: (number | null)[] = [null, 10, 15, 20];

function ParentGate({ challenge, onPass, onCancel }: { challenge: ParentChallenge; onPass: () => void; onCancel: () => void }) {
  const [typed, setTyped] = useState('');
  const [wrong, setWrong] = useState(false);
  const confirm = () => {
    if (Number(typed) === challenge.answer) {
      onPass();
    } else {
      setWrong(true);
      setTyped('');
    }
  };
  return (
    <main className="screen screen-center">
      <h2>어른 확인 🔒</h2>
      <p>아래 문제를 풀면 부모 설정이 열려요.</p>
      <div className="q-expr">
        <span>{challenge.a}</span>
        <span>×</span>
        <span>{challenge.b}</span>
        <span>=</span>
        <span className="slot">{typed || '?'}</span>
      </div>
      {wrong && <div className="error-text">다시 해보세요</div>}
      <Keypad
        value={typed}
        onChange={(v) => {
          setTyped(v);
          setWrong(false);
        }}
      />
      <Button3D full disabled={!typed} onClick={confirm}>
        확인
      </Button3D>
      <Button3D variant="white" full onClick={onCancel}>
        돌아가기
      </Button3D>
    </main>
  );
}

function ProfileAdmin({ profile }: { profile: Profile }) {
  const setStartStage = useGame((s) => s.setStartStage);
  const setUnlockAll = useGame((s) => s.setUnlockAll);
  const removeProfile = useGame((s) => s.removeProfile);
  const [start, setStart] = useState(STAGES[0].id);

  return (
    <section className="panel" aria-label={`${profile.name} 설정`}>
      <h3>
        {profile.avatar} {profile.name} · Lv.{levelFromXp(profile.xp)} · {profile.xp} XP
      </h3>
      <div className="stat-list">
        {(Object.keys(OP_NAMES) as Op[]).map((op) => {
          const s = profile.stats[op];
          const text = s.total ? `${Math.round((s.correct / s.total) * 100)}% (${s.correct}/${s.total})` : '-';
          return <div key={op}>{`${OP_NAMES[op]} ${text}`}</div>;
        })}
      </div>
      <div className="row">
        <select aria-label="시작 단계" value={start} onChange={(e) => setStart(e.target.value)}>
          {STAGES.map((s) => (
            <option key={s.id} value={s.id}>
              유닛 {s.unit} · {s.title}
            </option>
          ))}
        </select>
        <button className="small-btn" onClick={() => setStartStage(profile.id, start)}>
          여기부터 시작
        </button>
      </div>
      <label className="toggle">
        <input type="checkbox" checked={profile.unlockAll} onChange={(e) => setUnlockAll(profile.id, e.target.checked)} />
        모든 단계 열기
      </label>
      <button
        className="small-btn danger"
        onClick={() => {
          if (window.confirm(`${profile.name} 프로필을 지울까요? 기록이 모두 사라져요.`)) removeProfile(profile.id);
        }}
      >
        프로필 삭제
      </button>
    </section>
  );
}

export function Parent() {
  const nextSeed = useGame((s) => s.nextSeed);
  const data = useGame((s) => s.data);
  const loadError = useGame((s) => s.loadError);
  const hasProfile = useGame((s) => activeProfile(s) !== null);
  const goto = useGame((s) => s.goto);
  const setTimer = useGame((s) => s.setTimer);
  const setSound = useGame((s) => s.setSound);
  const [challenge] = useState(() => makeParentChallenge(mulberry32(nextSeed())));
  const [unlocked, setUnlocked] = useState(false);

  const close = () => goto(hasProfile ? { name: 'map' } : { name: 'profiles' });

  if (!unlocked) return <ParentGate challenge={challenge} onPass={() => setUnlocked(true)} onCancel={close} />;

  return (
    <main className="screen parent">
      <div className="parent-header">
        <h1>부모 설정</h1>
        <button className="small-btn" onClick={close}>
          닫기
        </button>
      </div>
      {loadError && <div className="notice">저장된 기록을 불러오지 못했어요. 새 기록으로 시작합니다.</div>}
      <section className="panel">
        <h3>타이머</h3>
        <div className="seg">
          {TIMER_OPTIONS.map((t) => (
            <button key={String(t)} aria-pressed={data.settings.timerSec === t} onClick={() => setTimer(t)}>
              {t === null ? '끔' : `${t}초`}
            </button>
          ))}
        </div>
        <label className="toggle">
          <input type="checkbox" checked={data.settings.soundOn} onChange={(e) => setSound(e.target.checked)} />
          효과음
        </label>
      </section>
      {data.profiles.map((p) => (
        <ProfileAdmin key={p.id} profile={p} />
      ))}
      <Button3D variant="blue" full onClick={() => goto({ name: 'profiles' })}>
        프로필 추가·바꾸기
      </Button3D>
    </main>
  );
}

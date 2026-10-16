import { useLiveQuery } from 'dexie-react-hooks';
import { useState } from 'react';
import { shortDate, todayLocal } from '../../core/date';
import { roundTo } from '../../core/metrics';
import { recommend } from '../../core/progression/rules';
import type { Exercise, OptionId, Segment, TargetOption, WeightTarget } from '../../core/types';
import {
  addWeightSet, deleteWeightSet, findSession, getOrCreateSession, listWeightSets, setSessionTarget,
  updateWeightSet, weightHistory,
} from '../../db/repository';
import { ScreenHeader } from '../components/ScreenHeader';
import { Stepper } from '../components/Stepper';
import { useDb } from '../DbContext';
import { exerciseLabel, formatKg, formatSet, formatWeightTarget } from '../format';
import type { Navigate } from '../routes';
import { RestTimerBar } from '../timer/RestTimerBar';
import { useRestTimer } from '../timer/useRestTimer';

export function WeightLog({ exercise, navigate }: { exercise: Exercise; navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const cfg = exercise.weight!;
  const data = useLiveQuery(async () => {
    const history = await weightHistory(db, exercise.id);
    const session = await findSession(db, exercise.id, today);
    const sets = session ? await listWeightSets(db, session.id) : [];
    return { history, session, sets };
  }, [db, exercise.id, today]);
  const timer = useRestTimer();
  const [optionId, setOptionId] = useState<OptionId | null>(null);
  const [draft, setDraft] = useState<Segment[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!data) return <p className="muted">불러오는 중…</p>;

  const rec = recommend(exercise, data.history, today);
  const options: TargetOption[] = rec.status === 'ok' ? rec.options : [];
  const savedKey = data.session?.target ? JSON.stringify(data.session.target) : null;
  const selected =
    options.find((o) => o.id === optionId) ?? options.find((o) => JSON.stringify(o.target) === savedKey) ?? options[0];
  const target = selected?.target as WeightTarget | undefined;
  const prev = data.history.filter((h) => h.date < today).at(-1);
  const index = data.sets.length;
  const targetSet = target?.sets[index];

  function prefill(): Segment[] {
    if (targetSet) return [{ weight: targetSet.weight, reps: targetSet.reps }];
    const lastToday = data!.sets.at(-1)?.segments[0];
    if (lastToday) return [{ ...lastToday }];
    const prevSet = prev?.sets[index]?.[0] ?? prev?.sets.at(-1)?.[0];
    if (prevSet) return [{ ...prevSet }];
    return [{ weight: 0, reps: cfg.repMin }];
  }
  const segments = draft ?? prefill();

  const updateSeg = (i: number, patch: Partial<Segment>) =>
    setDraft(segments.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const addDrop = () => {
    const last = segments[segments.length - 1];
    const goal = targetSet?.reps;
    setDraft([
      ...segments,
      {
        weight: Math.max(0, roundTo(last.weight - cfg.increment, cfg.increment)),
        reps: goal && goal > last.reps ? goal - last.reps : 1,
      },
    ]);
  };
  const resetEditor = () => {
    setDraft(null);
    setEditingId(null);
    setError(null);
  };

  async function complete() {
    try {
      setError(null);
      if (editingId) {
        await updateWeightSet(db, editingId, segments);
        resetEditor();
        return;
      }
      const session = await getOrCreateSession(db, exercise.id, today, target);
      await addWeightSet(db, session.id, segments);
      setDraft(null);
      timer.start(exercise.restSeconds);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove() {
    if (!editingId) return;
    await deleteWeightSet(db, editingId);
    resetEditor();
  }

  async function choose(o: TargetOption) {
    setOptionId(o.id);
    setDraft(null);
    if (data!.session) await setSessionTarget(db, data!.session.id, o.target);
  }

  const dropHint = target?.sets.find((s) => s.dropHint);

  return (
    <>
      <ScreenHeader title={exerciseLabel(exercise)} onBack={() => navigate({ name: 'today' })} />

      <section className="target-box" aria-label="오늘 목표">
        {rec.status === 'first' ? (
          <p>첫 기록이에요. 오늘 한 무게와 횟수를 입력하면 다음부터 목표를 추천해 드려요.</p>
        ) : (
          <>
            {rec.note && <p className="note">{rec.note}</p>}
            {options.length > 1 && (
              <div className="seg-toggle" role="group" aria-label="목표 선택">
                {options.map((o) => (
                  <button key={o.id} type="button" aria-pressed={o.id === selected?.id} onClick={() => choose(o)}>
                    {o.label}
                  </button>
                ))}
              </div>
            )}
            {target && <p className="target-text">목표: {formatWeightTarget(target)}</p>}
            {dropHint && (
              <p className="hint">지난번 드롭한 세트는 {formatKg(dropHint.weight)}kg에서 {dropHint.reps}회까지 버틴 뒤 무게를 바꿔 보세요.</p>
            )}
          </>
        )}
        {prev && (
          <p className="muted">지난번: {prev.sets.map(formatSet).join(' / ')} ({shortDate(prev.date)})</p>
        )}
      </section>

      <ol className="set-list">
        {data.sets.map((s, i) => (
          <li key={s.id}>
            <button type="button" className="set-row" onClick={() => { setEditingId(s.id); setDraft(s.segments.map((g) => ({ ...g }))); }}>
              <span>세트{i + 1} {formatSet(s.segments)}</span>
              <span className="ok">✔</span>
            </button>
          </li>
        ))}
      </ol>

      <section className="editor" aria-label="세트 입력">
        <h2>
          {editingId ? '세트 수정' : `세트${index + 1}`}
          {!editingId && targetSet && (
            <small>목표 {formatKg(targetSet.weight)}kg × {targetSet.reps}{targetSet.dropHint ? ' (후 드롭)' : ''}</small>
          )}
        </h2>
        {segments.map((seg, i) => (
          <div className="segment" key={i}>
            {i > 0 && (
              <div className="seg-label">
                <span>↳ 드롭 {i}</span>
                <button type="button" aria-label={`드롭 ${i} 삭제`} onClick={() => setDraft(segments.filter((_, j) => j !== i))}>×</button>
              </div>
            )}
            <Stepper label="무게" unit="kg" value={seg.weight} step={cfg.increment} onChange={(v) => updateSeg(i, { weight: v })} />
            <Stepper label="횟수" unit="회" value={seg.reps} step={1} min={1} integer onChange={(v) => updateSeg(i, { reps: v })} />
          </div>
        ))}
        <div className="row">
          <button type="button" onClick={addDrop}>무게 바꿈</button>
          <button type="button" className="primary" onClick={complete}>{editingId ? '저장' : '✔ 완료'}</button>
        </div>
        {editingId && (
          <div className="row">
            <button type="button" className="danger" onClick={remove}>삭제</button>
            <button type="button" onClick={resetEditor}>취소</button>
          </div>
        )}
        {error && <p role="alert" className="errors">{error}</p>}
      </section>

      <RestTimerBar timer={timer} />
    </>
  );
}

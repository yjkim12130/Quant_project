import { useLiveQuery } from 'dexie-react-hooks';
import { useId, useState } from 'react';
import { shortDate, todayLocal } from '../../core/date';
import { recommend } from '../../core/progression/rules';
import type { CardioEntry, CardioTarget, Exercise } from '../../core/types';
import { cardioHistory, findSession, getCardioEntry, getOrCreateSession, saveCardioEntry } from '../../db/repository';
import { ScreenHeader } from '../components/ScreenHeader';
import { Stepper } from '../components/Stepper';
import { useDb } from '../DbContext';
import { exerciseLabel, formatCardio } from '../format';
import type { Navigate } from '../routes';

interface Draft {
  minutes: number;
  intensity: Record<string, number>;
  distanceKm: string;
  kcal: string;
}

/** " · 3.6km · 210kcal" — 입력한 것만 */
function extras(v: { distanceKm?: number; kcal?: number }): string {
  return [v.distanceKm != null ? `${v.distanceKm}km` : null, v.kcal != null ? `${v.kcal}kcal` : null]
    .filter((s): s is string => s !== null)
    .map((s) => ` · ${s}`)
    .join('');
}

const fromEntry = (e: CardioEntry): Draft => ({
  minutes: e.minutes,
  intensity: { ...e.intensity },
  distanceKm: e.distanceKm != null ? String(e.distanceKm) : '',
  kcal: e.kcal != null ? String(e.kcal) : '',
});

export function CardioLog({ exercise, navigate }: { exercise: Exercise; navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const cfg = exercise.cardio!;
  const data = useLiveQuery(async () => {
    const history = await cardioHistory(db, exercise.id);
    const session = await findSession(db, exercise.id, today);
    const entry = session ? await getCardioEntry(db, session.id) : undefined;
    return { history, entry: entry ?? null };
  }, [db, exercise.id, today]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const distanceId = useId();
  const kcalId = useId();

  if (!data) return <p className="muted">불러오는 중…</p>;

  const rec = recommend(exercise, data.history, today);
  const target = rec.status === 'ok' ? (rec.options[0].target as CardioTarget) : undefined;
  const prev = data.history.filter((h) => h.date < today).at(-1);
  const base: Draft = data.entry
    ? fromEntry(data.entry)
    : {
        minutes: target?.minutes ?? prev?.minutes ?? cfg.minMinutes,
        intensity: Object.fromEntries(
          cfg.metrics.map((m) => [m.key, target?.intensity[m.key] ?? prev?.intensity[m.key] ?? 0]),
        ),
        distanceKm: '',
        kcal: '',
      };
  const v = draft ?? base;
  const showForm = !data.entry || editing;

  async function save() {
    try {
      setError(null);
      const session = await getOrCreateSession(db, exercise.id, today, target);
      await saveCardioEntry(db, session.id, {
        minutes: v.minutes,
        intensity: v.intensity,
        ...(v.distanceKm.trim() !== '' ? { distanceKm: Number(v.distanceKm) } : {}),
        ...(v.kcal.trim() !== '' ? { kcal: Number(v.kcal) } : {}),
      });
      setEditing(false);
      setDraft(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <ScreenHeader title={exerciseLabel(exercise)} onBack={() => navigate({ name: 'today' })} />

      <section className="target-box" aria-label="오늘 목표">
        {rec.status === 'first' ? (
          <p>첫 기록이에요. 오늘 한 시간과 강도를 입력하면 다음부터 목표를 추천해 드려요.</p>
        ) : (
          <>
            {rec.note && <p className="note">{rec.note}</p>}
            {target && <p className="target-text">{`목표: ${formatCardio(target, cfg.metrics)}`}</p>}
          </>
        )}
        {prev && (
          <p className="muted">{`지난번: ${formatCardio(prev, cfg.metrics)}${extras(prev)} (${shortDate(prev.date)})`}</p>
        )}
      </section>

      {!showForm && data.entry && (
        <section className="target-box" aria-label="오늘 기록">
          <p>{`오늘 기록: ${formatCardio(data.entry, cfg.metrics)}${extras(data.entry)}`}</p>
          <div className="row">
            <button type="button" onClick={() => { setDraft(fromEntry(data.entry!)); setEditing(true); }}>수정</button>
          </div>
        </section>
      )}

      {showForm && (
        <section className="editor" aria-label="유산소 입력">
          <Stepper label="시간" unit="분" value={v.minutes} step={1} min={1} integer onChange={(n) => setDraft({ ...v, minutes: n })} />
          {cfg.metrics.map((m) => (
            <Stepper
              key={m.key}
              label={m.label}
              unit={m.unit}
              value={v.intensity[m.key] ?? 0}
              step={m.step}
              onChange={(n) => setDraft({ ...v, intensity: { ...v.intensity, [m.key]: n } })}
            />
          ))}
          <div className="grid2">
            <div className="field">
              <span><label htmlFor={distanceId}>거리(km)</label></span>
              <input id={distanceId} type="number" inputMode="decimal" value={v.distanceKm}
                onChange={(e) => setDraft({ ...v, distanceKm: e.target.value })} />
            </div>
            <div className="field">
              <span><label htmlFor={kcalId}>칼로리(kcal)</label></span>
              <input id={kcalId} type="number" inputMode="numeric" value={v.kcal}
                onChange={(e) => setDraft({ ...v, kcal: e.target.value })} />
            </div>
          </div>
          <div className="row">
            <button type="button" className="primary" onClick={save}>저장</button>
            {editing && <button type="button" onClick={() => { setEditing(false); setDraft(null); }}>취소</button>}
          </div>
          {error && <p role="alert" className="errors">{error}</p>}
        </section>
      )}
    </>
  );
}

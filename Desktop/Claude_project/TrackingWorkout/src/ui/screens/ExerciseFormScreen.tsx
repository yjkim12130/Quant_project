import { useLiveQuery } from 'dexie-react-hooks';
import { useId, useState } from 'react';
import type { CardioConfig, CardioMetric, Exercise, WeightConfig } from '../../core/types';
import { addExercise, newId, updateExercise } from '../../db/repository';
import { NumberField } from '../components/NumberField';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import type { Navigate } from '../routes';
import { fromFormValues, toFormValues, validateExerciseForm, type ExerciseFormValues } from '../settings/exerciseForm';

export function ExerciseFormScreen({ exerciseId, navigate }: { exerciseId?: string; navigate: Navigate }) {
  const db = useDb();
  const loaded = useLiveQuery(
    async () => ({ ex: exerciseId ? await db.exercises.get(exerciseId) : undefined }),
    [db, exerciseId],
  );
  if (!loaded) return <p className="muted">불러오는 중…</p>;
  return <ExerciseForm original={loaded.ex} navigate={navigate} />;
}

function ExerciseForm({ original, navigate }: { original?: Exercise; navigate: Navigate }) {
  const db = useDb();
  const [v, setV] = useState<ExerciseFormValues>(() => toFormValues(original));
  const [errors, setErrors] = useState<string[]>([]);
  const equipmentId = useId();
  const nameId = useId();
  const back = () => navigate({ name: 'settings' });

  const setWeight = (patch: Partial<WeightConfig>) => setV((p) => ({ ...p, weight: { ...p.weight, ...patch } }));
  const setCardio = (patch: Partial<CardioConfig>) => setV((p) => ({ ...p, cardio: { ...p.cardio, ...patch } }));
  const setMetric = (i: number, patch: Partial<CardioMetric>) =>
    setCardio({ metrics: v.cardio.metrics.map((m, j) => (j === i ? { ...m, ...patch } : m)) });

  async function save() {
    const errs = validateExerciseForm(v);
    setErrors(errs);
    if (errs.length) return;
    try {
      const data = fromFormValues(v);
      if (original) {
        await updateExercise(db, { ...original, ...data });
      } else {
        await addExercise(db, data);
      }
      back();
    } catch (e) {
      setErrors([(e as Error).message]);
    }
  }

  async function toggleArchive() {
    if (!original) return;
    await updateExercise(db, { ...original, archived: !original.archived });
    back();
  }

  return (
    <>
      <ScreenHeader title={original ? '운동 수정' : '운동 추가'} onBack={back} />

      <div className="field">
        <span><label htmlFor={equipmentId}>기구 이름</label></span>
        <input id={equipmentId} type="text" placeholder="예: 레그프레스" value={v.equipment}
          onChange={(e) => setV({ ...v, equipment: e.target.value })} />
      </div>
      <div className="field">
        <span><label htmlFor={nameId}>운동 종류</label></span>
        <input id={nameId} type="text" placeholder="예: 하체" value={v.name}
          onChange={(e) => setV({ ...v, name: e.target.value })} />
      </div>

      <div className="seg-toggle" role="group" aria-label="운동 구분">
        {(['weight', 'cardio'] as const).map((k) => (
          <button key={k} type="button" aria-pressed={v.kind === k} disabled={!!original && original.kind !== k}
            onClick={() => setV({ ...v, kind: k })}>
            {k === 'weight' ? '웨이트' : '유산소'}
          </button>
        ))}
      </div>

      {v.kind === 'weight' ? (
        <>
          <div className="seg-toggle" role="group" aria-label="추천 방식">
            <button type="button" aria-pressed={v.weight.progression === 'double'} onClick={() => setWeight({ progression: 'double' })}>
              더블 프로그레션
            </button>
            <button type="button" aria-pressed={v.weight.progression === 'volume'} onClick={() => setWeight({ progression: 'volume' })}>
              볼륨 증가
            </button>
          </div>
          <p className="hint">
            {v.weight.progression === 'double'
              ? '모든 세트에서 최대 횟수를 채우면 무게를 올리고, 아니면 횟수를 1회씩 늘려요.'
              : '지난번 총 볼륨(무게×횟수)보다 증가율만큼 더 하도록 횟수안·무게안을 제시해요.'}
          </p>
          <div className="grid2">
            <NumberField label="최소 횟수" value={v.weight.repMin} onChange={(n) => setWeight({ repMin: n })} />
            <NumberField label="최대 횟수" value={v.weight.repMax} onChange={(n) => setWeight({ repMax: n })} />
            <NumberField label="목표 세트 수" value={v.weight.targetSets} onChange={(n) => setWeight({ targetSets: n })} />
            <NumberField label="증량 단위(kg)" step={0.5} value={v.weight.increment} onChange={(n) => setWeight({ increment: n })} />
            {v.weight.progression === 'volume' && (
              <NumberField label="볼륨 증가율(%)" value={v.weight.volumeGrowthPct} onChange={(n) => setWeight({ volumeGrowthPct: n })} />
            )}
          </div>
        </>
      ) : (
        <>
          <p className="hint">최대 시간을 채우면 ● 표시한 강도를 한 단계 올리고, 아니면 시간을 늘려요.</p>
          <div className="grid2">
            <NumberField label="최소 시간(분)" value={v.cardio.minMinutes} onChange={(n) => setCardio({ minMinutes: n })} />
            <NumberField label="최대 시간(분)" value={v.cardio.maxMinutes} onChange={(n) => setCardio({ maxMinutes: n })} />
            <NumberField label="시간 증가(분)" value={v.cardio.timeStep} onChange={(n) => setCardio({ timeStep: n })} />
          </div>
          <h2 className="section-title">강도 항목 (이름 · 단위 · 증가 단위 · ●올릴 항목)</h2>
          {v.cardio.metrics.map((m, i) => (
            <div className="metric-row" key={m.key}>
              <input type="text" aria-label="강도 항목 이름" placeholder="예: 속도" value={m.label}
                onChange={(e) => setMetric(i, { label: e.target.value })} />
              <input type="text" aria-label="단위" placeholder="km/h" value={m.unit}
                onChange={(e) => setMetric(i, { unit: e.target.value })} />
              <input type="number" inputMode="decimal" aria-label="증가 단위" value={Number.isNaN(m.step) ? '' : m.step}
                onChange={(e) => setMetric(i, { step: e.target.value === '' ? Number.NaN : Number(e.target.value) })} />
              <input type="radio" name="primary" aria-label="올릴 항목" checked={v.cardio.primaryMetric === m.key}
                onChange={() => setCardio({ primaryMetric: m.key })} />
              <button type="button" aria-label="항목 삭제"
                onClick={() => setCardio({ metrics: v.cardio.metrics.filter((_, j) => j !== i) })}>
                ×
              </button>
            </div>
          ))}
          <button type="button"
            onClick={() => setCardio({ metrics: [...v.cardio.metrics, { key: `m-${newId()}`, label: '', unit: '', step: 1 }] })}>
            + 강도 항목
          </button>
        </>
      )}

      <NumberField label="휴식 타이머(초)" value={v.restSeconds} onChange={(n) => setV({ ...v, restSeconds: n })} />

      {errors.length > 0 && (
        <ul className="errors" role="alert">
          {errors.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}

      <div className="row">
        <button type="button" className="primary" onClick={save}>저장</button>
      </div>
      {original && (
        <div className="row">
          <button type="button" onClick={toggleArchive}>{original.archived ? '다시 보이기' : '숨기기'}</button>
        </div>
      )}
    </>
  );
}

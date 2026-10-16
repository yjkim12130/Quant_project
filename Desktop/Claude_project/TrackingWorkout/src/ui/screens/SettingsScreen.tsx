import { useLiveQuery } from 'dexie-react-hooks';
import { useId, useState } from 'react';
import type { Exercise } from '../../core/types';
import { exportBackup, markBackedUp, parseBackup, restoreBackup } from '../../db/backup';
import { getMeta, listExercises } from '../../db/repository';
import { deliverBackup } from '../backupFile';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';

function ExerciseList({ items, navigate }: { items: Exercise[]; navigate: Navigate }) {
  return (
    <ul className="card-list">
      {items.map((ex) => (
        <li key={ex.id} className="card">
          <button type="button" className="card-main" onClick={() => navigate({ name: 'exerciseForm', exerciseId: ex.id })}>
            <span className="card-title">{exerciseLabel(ex)}</span>
            <span className="card-sub">{ex.kind === 'weight' ? '웨이트' : '유산소'}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getMonth() + 1}/${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function SettingsScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const exercises = useLiveQuery(() => listExercises(db, true), [db]);
  const backupInfo = useLiveQuery(async () => ({ at: await getMeta<string>(db, 'lastBackupAt') }), [db]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const importId = useId();
  const active = exercises?.filter((e) => !e.archived) ?? [];
  const archived = exercises?.filter((e) => e.archived) ?? [];

  async function doExport() {
    setError(null);
    const now = new Date();
    const result = await deliverBackup(await exportBackup(db, now), now);
    if (result === 'cancelled') {
      setMessage('백업을 취소했어요.');
      return;
    }
    await markBackedUp(db, now);
    setMessage('백업 파일을 저장했어요. 클라우드 드라이브나 메신저 "나에게 보내기"에 보관하세요.');
  }

  async function doImport(file: File | undefined) {
    if (!file) return;
    setError(null);
    setMessage(null);
    try {
      const backup = parseBackup(await file.text());
      if (!window.confirm('지금 기록을 모두 지우고 백업 내용으로 바꿉니다. 계속할까요?')) return;
      // 복원 전에 현재 데이터를 안전 백업으로 먼저 내보낸다
      const safety = await deliverBackup(await exportBackup(db));
      if (safety === 'cancelled') {
        setMessage('현재 기록을 먼저 백업해야 복원할 수 있어요. 복원을 취소했어요.');
        return;
      }
      await restoreBackup(db, backup);
      setMessage('백업을 복원했어요.');
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <ScreenHeader title="설정" />
      <h2 className="section-title">운동</h2>
      {exercises && active.length === 0 && <p className="muted">등록된 운동이 없어요.</p>}
      <ExerciseList items={active} navigate={navigate} />
      <div className="row">
        <button type="button" className="primary" onClick={() => navigate({ name: 'exerciseForm' })}>+ 운동 추가</button>
      </div>
      {archived.length > 0 && (
        <section aria-label="숨긴 운동">
          <h2 className="section-title">숨긴 운동</h2>
          <ExerciseList items={archived} navigate={navigate} />
        </section>
      )}

      <h2 className="section-title">백업</h2>
      <p className="muted">
        마지막 백업: {backupInfo?.at ? formatDateTime(backupInfo.at) : '없음'} · 폰을 바꾸거나 앱을 지우기 전에 꼭 백업하세요.
      </p>
      <div className="row">
        <button type="button" onClick={doExport}>백업 내보내기</button>
        <label htmlFor={importId} className="file-button">백업 가져오기</label>
        <input
          id={importId}
          type="file"
          accept="application/json,.json"
          style={{ display: 'none' }}
          onChange={(e) => {
            void doImport(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
      </div>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert" className="errors">{error}</p>}

      <p className="muted" style={{ marginTop: 24, fontSize: 13 }}>오늘도 +1 · 기록은 이 기기에만 저장돼요.</p>
    </>
  );
}

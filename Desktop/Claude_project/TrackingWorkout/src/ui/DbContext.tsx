import { createContext, useContext, type ReactNode } from 'react';
import type { WorkoutDB } from '../db/schema';

const DbContext = createContext<WorkoutDB | null>(null);

export function DbProvider({ db, children }: { db: WorkoutDB; children: ReactNode }) {
  return <DbContext.Provider value={db}>{children}</DbContext.Provider>;
}

export function useDb(): WorkoutDB {
  const db = useContext(DbContext);
  if (!db) throw new Error('DbProvider가 없습니다');
  return db;
}

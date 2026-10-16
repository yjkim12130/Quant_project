import Dexie, { type Table } from 'dexie';
import type { CardioEntry, Exercise, Session, WeightSetRecord } from '../core/types';

export interface MetaRow {
  key: string;
  value: unknown;
}

export class WorkoutDB extends Dexie {
  exercises!: Table<Exercise, string>;
  sessions!: Table<Session, string>;
  weightSets!: Table<WeightSetRecord, string>;
  cardioEntries!: Table<CardioEntry, string>;
  meta!: Table<MetaRow, string>;

  constructor(name = 'tracking-workout') {
    super(name);
    this.version(1).stores({
      exercises: 'id, &[equipment+name]',
      sessions: 'id, exerciseId, date, &[exerciseId+date]',
      weightSets: 'id, sessionId',
      cardioEntries: 'id, sessionId',
      meta: 'key',
    });
  }
}

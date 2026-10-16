import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import type { WorkoutDB } from '../db/schema';
import { DbProvider } from '../ui/DbContext';
import { makeTestDb } from './testDb';

export function renderApp(db: WorkoutDB = makeTestDb()) {
  const user = userEvent.setup();
  const result = render(
    <DbProvider db={db}>
      <App />
    </DbProvider>,
  );
  return { ...result, db, user };
}

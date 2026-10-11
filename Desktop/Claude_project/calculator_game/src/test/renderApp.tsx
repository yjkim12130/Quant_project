import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { GameProvider } from '../state/GameContext';
import { createGameStore, type GameStore } from '../state/store';
import { MemoryKV } from './memoryKV';

export function renderApp(opts: { kv?: MemoryKV; setup?: (store: GameStore) => void } = {}) {
  const kv = opts.kv ?? new MemoryKV();
  let n = 0;
  const store = createGameStore({ kv, nextSeed: () => 42, today: () => '2026-10-10', makeId: () => `p${++n}` });
  opts.setup?.(store);
  const user = userEvent.setup();
  render(
    <GameProvider store={store}>
      <App />
    </GameProvider>,
  );
  return { store, kv, user };
}

export async function typeNumber(user: ReturnType<typeof userEvent.setup>, n: number) {
  for (const d of String(n)) await user.click(screen.getByRole('button', { name: `숫자 ${d}` }));
}

export const withProfile = (store: GameStore) => store.getState().addProfile('하늘', '🐶');

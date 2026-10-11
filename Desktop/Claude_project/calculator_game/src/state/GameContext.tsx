import { createContext, useContext, type ReactNode } from 'react';
import { useStore } from 'zustand';
import type { GameState, GameStore } from './store';

const GameContext = createContext<GameStore | null>(null);

export function GameProvider({ store, children }: { store: GameStore; children: ReactNode }) {
  return <GameContext.Provider value={store}>{children}</GameContext.Provider>;
}

// selector는 기존 객체 참조나 원시값만 돌려줘야 한다 (새 객체를 만들면 무한 렌더)
export function useGame<T>(selector: (s: GameState) => T): T {
  const store = useContext(GameContext);
  if (!store) throw new Error('GameProvider 안에서만 useGame을 쓸 수 있어요');
  return useStore(store, selector);
}

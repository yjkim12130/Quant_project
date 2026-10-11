import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { browserStorage } from './core/storage';
import { GameProvider } from './state/GameContext';
import { createGameStore } from './state/store';
import './ui/theme.css';

const store = createGameStore({ kv: browserStorage() });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GameProvider store={store}>
      <App />
    </GameProvider>
  </StrictMode>,
);

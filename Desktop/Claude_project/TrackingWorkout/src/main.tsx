import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { WorkoutDB } from './db/schema';
import { DbProvider } from './ui/DbContext';
import './ui/theme.css';

const db = new WorkoutDB();
// 브라우저가 저장소를 임의로 비우지 않도록 요청(특히 iOS)
navigator.storage?.persist?.().catch(() => undefined);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DbProvider db={db}>
      <App />
    </DbProvider>
  </StrictMode>,
);

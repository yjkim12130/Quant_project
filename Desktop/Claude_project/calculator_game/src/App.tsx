import { useGame } from './state/GameContext';
import { activeProfile } from './state/store';
import { Lesson } from './ui/screens/Lesson';
import { Parent } from './ui/screens/Parent';
import { ProfileSelect } from './ui/screens/ProfileSelect';
import { Result } from './ui/screens/Result';
import { StageMap } from './ui/screens/StageMap';

export function App() {
  const screen = useGame((s) => s.screen);
  const profile = useGame(activeProfile);

  let content;
  if (screen.name === 'parent') content = <Parent />;
  else if (!profile || screen.name === 'profiles') content = <ProfileSelect />;
  else if (screen.name === 'lesson') content = <Lesson stageId={screen.stageId} />;
  else if (screen.name === 'result') content = <Result stageId={screen.stageId} summary={screen.summary} />;
  else content = <StageMap />;

  return <div className="app">{content}</div>;
}

import { useGame } from './state/GameContext';
import { activeProfile } from './state/store';
import { Category } from './ui/screens/Category';
import { Home } from './ui/screens/Home';
import { Intro } from './ui/screens/Intro';
import { Lesson } from './ui/screens/Lesson';
import { Parent } from './ui/screens/Parent';
import { ProfileSelect } from './ui/screens/ProfileSelect';
import { Result } from './ui/screens/Result';

export function App() {
  const screen = useGame((s) => s.screen);
  const profile = useGame(activeProfile);

  let content;
  if (screen.name === 'intro') content = <Intro />;
  else if (screen.name === 'parent') content = <Parent />;
  else if (!profile || screen.name === 'profiles') content = <ProfileSelect />;
  else if (screen.name === 'lesson') content = <Lesson key={screen.stageId} stageId={screen.stageId} categoryId={screen.categoryId} />;
  else if (screen.name === 'result')
    content = <Result stageId={screen.stageId} categoryId={screen.categoryId} summary={screen.summary} />;
  else if (screen.name === 'category') content = <Category categoryId={screen.categoryId} />;
  else content = <Home />;

  return <div className="app">{content}</div>;
}

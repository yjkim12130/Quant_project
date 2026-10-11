import { levelFromXp } from '../../core/scoring';
import { displayStreak } from '../../core/streak';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';

export function TopBar() {
  const profile = useGame(activeProfile);
  const soundOn = useGame((s) => s.data.settings.soundOn);
  const setSound = useGame((s) => s.setSound);
  const goto = useGame((s) => s.goto);
  const today = useGame((s) => s.today);
  if (!profile) return null;
  const streak = displayStreak(profile.streak, today());
  const level = levelFromXp(profile.xp);
  return (
    <header className="topbar">
      <button className="chip" aria-label="프로필 바꾸기" onClick={() => goto({ name: 'profiles' })}>
        {profile.avatar}
      </button>
      <span className="chip chip-fire" aria-label={`연속 ${streak}일`}>🔥 {streak}</span>
      <span className="chip chip-xp" aria-label={`레벨 ${level}, ${profile.xp} XP`}>⭐ Lv.{level}</span>
      <span className="spacer" />
      <button className="chip" aria-label={soundOn ? '소리 끄기' : '소리 켜기'} onClick={() => setSound(!soundOn)}>
        {soundOn ? '🔊' : '🔇'}
      </button>
      <button className="chip" aria-label="부모 설정" onClick={() => goto({ name: 'parent' })}>
        ⚙️
      </button>
    </header>
  );
}

import { useState } from 'react';
import { useGame } from '../../state/GameContext';
import { Button3D } from '../components/Button3D';
import { Mascot } from '../components/Mascot';

const AVATARS = ['🐶', '🐱', '🐰', '🦊', '🐼', '🐯', '🐸', '🐵'];

export function ProfileSelect() {
  const profiles = useGame((s) => s.data.profiles);
  const selectProfile = useGame((s) => s.selectProfile);
  const addProfile = useGame((s) => s.addProfile);
  const [adding, setAdding] = useState(profiles.length === 0);
  const [name, setName] = useState('');
  const [avatar, setAvatar] = useState(AVATARS[0]);

  return (
    <main className="screen screen-center">
      <Mascot mood="happy" speech={adding ? '이름을 알려줘!' : '누가 공부할까?'} />
      <h1 className="title">셈셈 병아리</h1>
      {adding ? (
        <form
          className="add-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) addProfile(name, avatar);
          }}
        >
          <input
            className="name-input"
            aria-label="이름"
            placeholder="이름"
            maxLength={8}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="avatar-row">
            {AVATARS.map((a) => (
              <button
                key={a}
                type="button"
                className={`avatar-pick ${a === avatar ? 'on' : ''}`}
                aria-label={`아바타 ${a}`}
                aria-pressed={a === avatar}
                onClick={() => setAvatar(a)}
              >
                {a}
              </button>
            ))}
          </div>
          <Button3D type="submit" full disabled={!name.trim()}>
            시작하기
          </Button3D>
          {profiles.length > 0 && (
            <Button3D variant="white" full onClick={() => setAdding(false)}>
              취소
            </Button3D>
          )}
        </form>
      ) : (
        <div className="profile-grid">
          {profiles.map((p) => (
            <button key={p.id} className="profile-card" onClick={() => selectProfile(p.id)}>
              <span className="profile-avatar">{p.avatar}</span>
              <span className="display">{p.name}</span>
            </button>
          ))}
          <button className="profile-card" aria-label="프로필 추가" onClick={() => setAdding(true)}>
            <span className="profile-avatar">＋</span>
            <span className="display">추가</span>
          </button>
        </div>
      )}
    </main>
  );
}

export function ScreenHeader({ title, onBack }: { title: string; onBack?: () => void }) {
  return (
    <header className="screen-header">
      {onBack && (
        <button type="button" className="back" aria-label="뒤로" onClick={onBack}>
          ←
        </button>
      )}
      <h1>{title}</h1>
    </header>
  );
}

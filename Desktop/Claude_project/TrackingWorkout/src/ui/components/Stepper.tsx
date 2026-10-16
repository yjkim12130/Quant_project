import { useId, useState } from 'react';

const fix = (n: number) => Number(n.toFixed(3));

export function Stepper({
  label, unit, value, step, min = 0, integer = false, onChange,
}: {
  label: string; unit: string; value: number; step: number; min?: number; integer?: boolean;
  onChange: (v: number) => void;
}) {
  const id = useId();
  // 입력 중인 문자열("4", "42.")을 유지하고, 포커스가 빠지면 value로 되돌린다
  const [text, setText] = useState<string | null>(null);
  const clamp = (n: number) => Math.max(min, integer ? Math.round(n) : fix(n));

  return (
    <div className="stepper">
      <label htmlFor={id}>{label}{unit && <small className="muted"> {unit}</small>}</label>
      <button type="button" aria-label={`${label} 감소`} onClick={() => { setText(null); onChange(clamp(value - step)); }}>−</button>
      <input
        id={id}
        type="number"
        inputMode={integer ? 'numeric' : 'decimal'}
        aria-label={label}
        value={text ?? String(value)}
        onChange={(e) => {
          setText(e.target.value);
          const n = Number(e.target.value);
          if (e.target.value !== '' && Number.isFinite(n)) onChange(clamp(n));
        }}
        onBlur={() => setText(null)}
      />
      <button type="button" aria-label={`${label} 증가`} onClick={() => { setText(null); onChange(clamp(value + step)); }}>+</button>
    </div>
  );
}

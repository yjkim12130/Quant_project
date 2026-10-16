import { useId } from 'react';

export function NumberField({
  label, value, onChange, step = 1,
}: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  const id = useId();
  return (
    <div className="field">
      <span>
        <label htmlFor={id}>{label}</label>
      </span>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        step={step}
        value={Number.isNaN(value) ? '' : value}
        onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))}
      />
    </div>
  );
}

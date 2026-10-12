const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'del'];
const MAX_DIGITS = 3;

interface Props {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function Keypad({ value, onChange, disabled }: Props) {
  const press = (key: string) => {
    if (key === 'del') onChange(value.slice(0, -1));
    else if (value === '0') onChange(key);
    else if (value.length < MAX_DIGITS) onChange(value + key);
  };
  return (
    <div className="keypad">
      {KEYS.map((key, i) =>
        key === '' ? (
          <span key={`blank-${i}`} />
        ) : (
          <button
            key={key}
            type="button"
            className="key"
            disabled={disabled}
            aria-label={key === 'del' ? '지우기' : `숫자 ${key}`}
            onClick={() => press(key)}
          >
            {key === 'del' ? '⌫' : key}
          </button>
        ),
      )}
    </div>
  );
}

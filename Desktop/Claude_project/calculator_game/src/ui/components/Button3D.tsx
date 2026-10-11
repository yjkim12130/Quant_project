import type { ButtonHTMLAttributes } from 'react';

type Variant = 'green' | 'blue' | 'red' | 'yellow' | 'white';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  full?: boolean;
  selected?: boolean;
}

export function Button3D({ variant = 'green', full, selected, className = '', type = 'button', ...rest }: Props) {
  const cls = ['btn', `btn-${variant}`, full && 'btn-full', selected && 'btn-selected', className].filter(Boolean).join(' ');
  return <button type={type} className={cls} {...rest} />;
}

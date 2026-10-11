import type { ReactNode } from 'react';
import { OP_SYMBOL } from '../../core/generator';
import type { Question } from '../../core/types';
import { Button3D } from './Button3D';

interface Props {
  q: Question;
  typed: string;
  selected: number | null;
  onSelect: (value: number) => void;
  disabled: boolean;
}

function prompt(q: Question): string {
  if (q.kind === 'blank') return '빈칸에 들어갈 수는?';
  if (q.kind === 'picture') return q.op === 'add' ? '모두 몇 개일까?' : '남은 건 몇 개일까?';
  return '정답은?';
}

function Pictures({ q }: { q: Question }) {
  if (q.op === 'add') {
    return (
      <div className="pics" aria-hidden>
        <span className="pic-group">{Array.from({ length: q.a }, (_, i) => <span key={i}>🍎</span>)}</span>
        <span className="pic-op">+</span>
        <span className="pic-group">{Array.from({ length: q.b }, (_, i) => <span key={i}>🍎</span>)}</span>
      </div>
    );
  }
  return (
    <div className="pics" aria-hidden>
      <span className="pic-group">
        {Array.from({ length: q.a }, (_, i) => (
          <span key={i} className={i >= q.a - q.b ? 'pic-gone' : ''}>🍪</span>
        ))}
      </span>
    </div>
  );
}

export function QuestionView({ q, typed, selected, onSelect, disabled }: Props) {
  const isChoice = q.kind === 'choice' || q.kind === 'picture';
  const slot = (content: ReactNode) => <span className="slot">{content}</span>;
  return (
    <div className="question">
      <div className="q-prompt">{prompt(q)}</div>
      {q.kind === 'picture' && <Pictures q={q} />}
      <div className="q-expr">
        <span>{q.a}</span>
        <span>{OP_SYMBOL[q.op]}</span>
        {q.kind === 'blank' ? slot(typed || '?') : <span>{q.b}</span>}
        <span>=</span>
        {q.kind === 'blank' ? <span>{q.result}</span> : slot(isChoice ? (selected ?? '?') : typed || '?')}
      </div>
      {isChoice && q.choices && (
        <div className="choices">
          {q.choices.map((c) => (
            <Button3D key={c} variant="white" selected={selected === c} disabled={disabled} onClick={() => onSelect(c)}>
              {c}
            </Button3D>
          ))}
        </div>
      )}
    </div>
  );
}

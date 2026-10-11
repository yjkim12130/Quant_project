import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { Button3D } from './Button3D';
import { ProgressBar } from './ProgressBar';
import { Hearts } from './Hearts';
import { Keypad } from './Keypad';
import { FeedbackSheet } from './FeedbackSheet';
import { Mascot } from './Mascot';
import { playCorrect, playFanfare, playWrong, vibrate } from '../../audio/sfx';

function KeypadHarness() {
  const [v, setV] = useState('');
  return (
    <>
      <output>{v}</output>
      <Keypad value={v} onChange={setV} />
    </>
  );
}

describe('components', () => {
  it('Button3D는 변형·선택 클래스를 붙인다', () => {
    render(<Button3D variant="white" selected full>7</Button3D>);
    const btn = screen.getByRole('button', { name: '7' });
    expect(btn).toHaveClass('btn', 'btn-white', 'btn-selected', 'btn-full');
    expect(btn).toHaveAttribute('type', 'button');
  });

  it('ProgressBar는 퍼센트를 알려준다', () => {
    render(<ProgressBar value={0.3} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '30');
  });

  it('Hearts는 개수를 읽어준다', () => {
    render(<Hearts count={3} />);
    expect(screen.getByLabelText('하트 3개')).toBeInTheDocument();
  });

  it('Keypad는 숫자 입력·지우기·3자리 제한', async () => {
    const user = userEvent.setup();
    render(<KeypadHarness />);
    for (const d of ['1', '2', '3', '4']) await user.click(screen.getByRole('button', { name: `숫자 ${d}` }));
    expect(screen.getByRole('status')).toHaveTextContent('123');
    await user.click(screen.getByRole('button', { name: '지우기' }));
    expect(screen.getByRole('status')).toHaveTextContent('12');
  });

  it('Keypad는 0 다음 숫자를 누르면 0을 바꾼다', async () => {
    const user = userEvent.setup();
    render(<KeypadHarness />);
    await user.click(screen.getByRole('button', { name: '숫자 0' }));
    await user.click(screen.getByRole('button', { name: '숫자 5' }));
    expect(screen.getByRole('status')).toHaveTextContent('5');
  });

  it('FeedbackSheet: 오답이면 정답과 격려, 계속 버튼', async () => {
    const user = userEvent.setup();
    const onContinue = vi.fn();
    render(<FeedbackSheet correct={false} timedOut={false} correctText="8" message="한 번 더 나올 거야" onContinue={onContinue} />);
    expect(screen.getByText('괜찮아, 다시 해보자!')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '계속' }));
    expect(onContinue).toHaveBeenCalledOnce();
  });

  it('FeedbackSheet: 정답이면 정답 줄을 숨긴다', () => {
    render(<FeedbackSheet correct timedOut={false} correctText="8" message="" onContinue={() => {}} />);
    expect(screen.getByText('잘했어! 🎉')).toBeInTheDocument();
    expect(screen.queryByText(/정답:/)).toBeNull();
  });

  it('Mascot은 말풍선을 보여준다', () => {
    render(<Mascot mood="happy" speech="안녕!" />);
    expect(screen.getByText('안녕!')).toBeInTheDocument();
  });

  it('효과음은 AudioContext가 없어도 에러 없이 넘어간다', () => {
    expect(() => { playCorrect(); playWrong(); playFanfare(); vibrate(50); }).not.toThrow();
  });
});

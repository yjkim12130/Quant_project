import { motion } from 'framer-motion';
import { Button3D } from './Button3D';

interface Props {
  correct: boolean;
  timedOut: boolean;
  message: string;
  onContinue: () => void;
}

export function FeedbackSheet({ correct, timedOut, message, onContinue }: Props) {
  const title = correct ? '잘했어! 🎉' : timedOut ? '시간이 다 됐어!' : '괜찮아, 다시 해보자!';
  return (
    <motion.div
      className={`sheet ${correct ? 'sheet-ok' : 'sheet-bad'}`}
      initial={{ y: '100%' }}
      animate={{ y: 0 }}
      transition={{ type: 'spring', damping: 22, stiffness: 260 }}
    >
      <div className="sheet-title display">{title}</div>
      {/* 오답이어도 정답은 알려주지 않는다 — 복습 때 스스로 다시 풀게 한다 */}
      {message && <div className="sheet-msg">{message}</div>}
      <Button3D variant={correct ? 'green' : 'red'} full onClick={onContinue}>
        계속
      </Button3D>
    </motion.div>
  );
}

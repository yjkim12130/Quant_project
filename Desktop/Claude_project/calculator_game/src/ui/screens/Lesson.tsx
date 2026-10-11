import { useEffect, useState } from 'react';
import { generateLesson } from '../../core/generator';
import { currentItem, lessonProgress, nextQuestion, startLesson, submitAnswer, toOutcome } from '../../core/lesson';
import { getStage } from '../../core/stages';
import { playCorrect, playFanfare, playWrong, vibrate } from '../../audio/sfx';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { Button3D } from '../components/Button3D';
import { FeedbackSheet } from '../components/FeedbackSheet';
import { Hearts } from '../components/Hearts';
import { Keypad } from '../components/Keypad';
import { Mascot, type Mood } from '../components/Mascot';
import { ProgressBar } from '../components/ProgressBar';
import { QuestionView } from '../components/QuestionView';

export function Lesson({ stageId }: { stageId: string }) {
  const stage = getStage(stageId);
  const profile = useGame(activeProfile);
  const nextSeed = useGame((s) => s.nextSeed);
  const settings = useGame((s) => s.data.settings);
  const goto = useGame((s) => s.goto);
  const finishLesson = useGame((s) => s.finishLesson);

  const [lesson, setLesson] = useState(() =>
    startLesson(generateLesson(stage, profile?.stages[stageId]?.crowns ?? 0, nextSeed())),
  );
  const [selected, setSelected] = useState<number | null>(null);
  const [typed, setTyped] = useState('');
  const [left, setLeft] = useState<number | null>(null);

  const item = currentItem(lesson);
  const answering = lesson.phase === 'answering';
  const isChoice = item?.q.kind === 'choice' || item?.q.kind === 'picture';

  const check = (value: number | null) => {
    if (lesson.phase !== 'answering') return;
    const next = submitAnswer(lesson, value);
    setLesson(next);
    if (next.last?.correct) {
      if (settings.soundOn) playCorrect();
    } else {
      if (settings.soundOn) playWrong();
      vibrate(80);
    }
  };

  const onConfirm = () => {
    if (isChoice) {
      if (selected !== null) check(selected);
    } else if (typed !== '') {
      check(Number(typed));
    }
  };

  const onContinue = () => {
    const next = nextQuestion(lesson);
    setSelected(null);
    setTyped('');
    if (next.phase === 'done') {
      if (settings.soundOn) playFanfare();
      finishLesson(stageId, toOutcome(next));
      return;
    }
    setLesson(next);
  };

  // 타이머 (부모 설정에서 켰을 때만)
  useEffect(() => {
    if (!settings.timerSec || lesson.phase !== 'answering') {
      setLeft(null);
      return;
    }
    const limit = settings.timerSec;
    const started = Date.now();
    setLeft(limit);
    const id = setInterval(() => setLeft(limit - Math.floor((Date.now() - started) / 1000)), 250);
    return () => clearInterval(id);
  }, [lesson.index, lesson.phase, settings.timerSec]);

  useEffect(() => {
    // check는 매 렌더 새로 만들어지므로 left 변화에만 반응한다
    if (left !== null && left <= 0) check(null);
  }, [left]);

  const last = lesson.last;
  const mood: Mood = lesson.phase === 'feedback' ? (last?.correct ? 'happy' : 'cheer') : 'idle';
  let message = '';
  if (lesson.phase === 'feedback' && last) {
    if (last.correct && lesson.inARow >= 3) message = `${lesson.inARow}개 연속! 불붙었다 🔥`;
    else if (!last.correct && !last.review && !last.timedOut && lesson.hearts === 0)
      message = '하트가 다 떨어졌어. 잠깐 쉬어가자! 그래도 끝까지 풀어보자 💪';
    else if (!last.correct && !last.review) message = '이 문제는 마지막에 한 번 더 나올 거야.';
  }

  return (
    <main className="screen lesson">
      <div className="lesson-top">
        <button className="icon-btn" aria-label="그만하기" onClick={() => goto({ name: 'map' })}>
          ✕
        </button>
        <ProgressBar value={lessonProgress(lesson)} />
        <Hearts count={lesson.hearts} />
      </div>
      {left !== null && (
        <div className="timer" aria-label={`남은 시간 ${Math.max(0, left)}초`}>
          ⏱ {Math.max(0, left)}
        </div>
      )}
      {item && (
        <>
          {item.review && <div className="review-tag">다시 풀어보기</div>}
          {stage.hint && lesson.index === 0 && <div className="hint">{stage.hint}</div>}
          <QuestionView q={item.q} typed={typed} selected={selected} onSelect={setSelected} disabled={!answering} />
          <Mascot mood={mood} size={72} />
          {!isChoice && <Keypad value={typed} onChange={setTyped} disabled={!answering} />}
        </>
      )}
      <div className="lesson-bottom">
        {answering && (
          <Button3D full disabled={isChoice ? selected === null : typed === ''} onClick={onConfirm}>
            확인
          </Button3D>
        )}
      </div>
      {lesson.phase === 'feedback' && last && item && (
        <FeedbackSheet
          correct={last.correct}
          timedOut={last.timedOut}
          correctText={String(item.q.answer)}
          message={message}
          onContinue={onContinue}
        />
      )}
    </main>
  );
}

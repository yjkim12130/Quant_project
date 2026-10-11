type AudioCtor = typeof AudioContext;
let ctx: AudioContext | null = null;

function audio(): AudioContext | null {
  if (ctx) return ctx;
  const AC: AudioCtor | undefined =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext;
  if (!AC) return null;
  try {
    ctx = new AC();
  } catch {
    return null;
  }
  return ctx;
}

function tone(freq: number, at: number, dur: number, type: OscillatorType = 'sine', vol = 0.18) {
  const c = audio();
  if (!c) return;
  if (c.state === 'suspended') void c.resume();
  const t = c.currentTime + at;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(vol, t + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(gain).connect(c.destination);
  osc.start(t);
  osc.stop(t + dur + 0.05);
}

export function playCorrect() {
  tone(784, 0, 0.18);
  tone(1175, 0.12, 0.3);
}

export function playWrong() {
  tone(330, 0, 0.15, 'square', 0.08);
  tone(220, 0.12, 0.25, 'square', 0.08);
}

export function playFanfare() {
  [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.12, i === 3 ? 0.5 : 0.18, 'triangle'));
}

export function vibrate(ms: number) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    // 진동 미지원 기기
  }
}

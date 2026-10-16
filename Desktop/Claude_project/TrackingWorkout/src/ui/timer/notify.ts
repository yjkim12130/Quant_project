/** 휴식 종료 알림: 진동(안드로이드만) + 짧은 비프음. 실패해도 조용히 넘어간다 */
export function notifyRestDone(): void {
  try {
    navigator.vibrate?.([200, 100, 200]);
  } catch {
    // 진동 미지원
  }
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.value = 0.2;
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
    osc.onended = () => void ctx.close();
  } catch {
    // 소리 재생 실패는 무시
  }
}

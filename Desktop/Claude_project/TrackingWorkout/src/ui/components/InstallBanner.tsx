export function shouldShowInstallHint(userAgent: string, standalone: boolean): boolean {
  return /iPhone|iPad|iPod/.test(userAgent) && !standalone;
}

export function InstallBanner() {
  const standalone =
    window.matchMedia?.('(display-mode: standalone)')?.matches === true ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  if (!shouldShowInstallHint(navigator.userAgent, standalone)) return null;
  return (
    <div className="banner" role="note">
      <span>Safari 공유 버튼 → <b>홈 화면에 추가</b>로 설치해야 기록이 안전하게 보관돼요.</span>
    </div>
  );
}

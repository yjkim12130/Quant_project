import { expect, it } from 'vitest';
import { shouldShowInstallHint } from './InstallBanner';

it('iOS Safari 탭에서만 설치 안내', () => {
  const iphone = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
  expect(shouldShowInstallHint(iphone, false)).toBe(true);
  expect(shouldShowInstallHint(iphone, true)).toBe(false);
  expect(shouldShowInstallHint('Mozilla/5.0 (Linux; Android 15)', false)).toBe(false);
});

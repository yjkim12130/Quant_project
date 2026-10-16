import { screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { renderApp } from './test/renderApp';

it('하단 탭으로 화면을 전환한다', async () => {
  const { user } = renderApp();
  expect(screen.getByRole('button', { name: '오늘' })).toHaveAttribute('aria-current', 'page');
  await user.click(screen.getByRole('button', { name: '설정' }));
  expect(screen.getByRole('button', { name: '설정' })).toHaveAttribute('aria-current', 'page');
  await user.click(screen.getByRole('button', { name: '기록' }));
  expect(screen.getByRole('button', { name: '기록' })).toHaveAttribute('aria-current', 'page');
});

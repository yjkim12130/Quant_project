import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { App } from './App';

it('앱 이름을 보여준다', () => {
  render(<App />);
  expect(screen.getByText('오늘도 +1')).toBeInTheDocument();
});

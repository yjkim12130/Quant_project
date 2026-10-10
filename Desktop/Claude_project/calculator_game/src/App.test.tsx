import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { App } from './App';

describe('App', () => {
  it('앱 제목을 보여준다', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: '셈셈 병아리' })).toBeInTheDocument();
  });
});

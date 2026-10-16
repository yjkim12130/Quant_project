import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRestTimer } from './useRestTimer';

describe('useRestTimer', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('카운트다운 후 종료 알림', () => {
    const onFinish = vi.fn();
    const { result } = renderHook(() => useRestTimer(onFinish));
    expect(result.current.remaining).toBeNull();
    act(() => result.current.start(90));
    expect(result.current.remaining).toBe(90);
    act(() => vi.advanceTimersByTime(30_000));
    expect(result.current.remaining).toBe(60);
    act(() => result.current.add(15));
    act(() => vi.advanceTimersByTime(250));
    expect(result.current.remaining).toBe(75);
    act(() => vi.advanceTimersByTime(75_000));
    expect(result.current.remaining).toBeNull();
    expect(result.current.finished).toBe(true);
    expect(onFinish).toHaveBeenCalledTimes(1);
    act(() => result.current.skip());
    expect(result.current.finished).toBe(false);
  });
  it('건너뛰기', () => {
    const onFinish = vi.fn();
    const { result } = renderHook(() => useRestTimer(onFinish));
    act(() => result.current.start(60));
    act(() => result.current.skip());
    act(() => vi.advanceTimersByTime(61_000));
    expect(result.current.remaining).toBeNull();
    expect(onFinish).not.toHaveBeenCalled();
  });
});

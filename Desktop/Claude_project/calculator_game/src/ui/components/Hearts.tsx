export function Hearts({ count }: { count: number }) {
  return (
    <div className="hearts" aria-label={`하트 ${count}개`}>
      ❤️ <span>{count}</span>
    </div>
  );
}

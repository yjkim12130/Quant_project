/** 아이를 부르는 이름: 마지막 글자에 받침이 있으면 '이'를 붙인다 (동현 → 동현이, 지우 → 지우). */
export function callName(name: string): string {
  const n = name.trim();
  const code = n.charCodeAt(n.length - 1) - 0xac00;
  const isHangul = code >= 0 && code <= 11171;
  return isHangul && code % 28 !== 0 ? `${n}이` : n;
}

/** Стабильный hash для подписи столбца → постоянный цвет при пересортировке. */
function hashLabel(label: string): number {
  let h = 2166136261;
  const s = label.trim().toLowerCase();
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/**
 * Оттенки в сине-бирюзовой гамме (различимы, но не «радуга»).
 * index — порядковый номер для дополнительного разнесения при совпадениях.
 */
export function barColorForLabel(label: string, index = 0): string {
  const h = hashLabel(label);
  const slot = (h + index * 13) % 28;
  const hue = 198 + (slot % 14) * 5 + Math.floor(slot / 14) * 3; // ~198–263
  const lightness = 40 + (slot % 7) * 4; // 40–64
  const saturation = 48 + (Math.floor(slot / 7) % 4) * 9; // 48–75
  return `hsl(${hue} ${saturation}% ${lightness}%)`;
}

export function withBarColors<T extends { label: string; color?: string }>(
  items: T[],
): T[] {
  return items.map((item, i) => ({
    ...item,
    color: item.color ?? barColorForLabel(item.label, i),
  }));
}

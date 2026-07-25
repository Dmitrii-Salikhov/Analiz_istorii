import './BarChart.css';

export type BarItem = { label: string; value: number; color?: string };

export function BarChart({
  items,
  unit = '',
  height = 180,
}: {
  items: BarItem[];
  unit?: string;
  height?: number;
}) {
  const max = Math.max(...items.map((i) => i.value), 1);
  if (!items.length) {
    return <div className="bar-empty">Нет данных для графика</div>;
  }
  return (
    <div className="bar-chart" style={{ minHeight: height }}>
      {items.map((item) => (
        <div className="bar-col" key={item.label} title={`${item.label}: ${item.value}${unit}`}>
          <div className="bar-value">
            {Number.isInteger(item.value) ? item.value : item.value.toFixed(1)}
            {unit}
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{
                height: `${Math.max(4, (item.value / max) * 100)}%`,
                background: item.color || 'var(--accent)',
              }}
            />
          </div>
          <div className="bar-label">{item.label}</div>
        </div>
      ))}
    </div>
  );
}

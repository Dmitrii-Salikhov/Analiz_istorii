import './BarChart.css';

export type BarItem = { label: string; value: number; color?: string };

export type BarSeries = { key: string; value: number; color?: string };

/** Одна группа: общая подпись + несколько столбцов рядом (напр. с/без СНИЛС). */
export type BarGroup = {
  label: string;
  series: BarSeries[];
};

function fmtValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function BarChart({
  items,
  groups,
  unit = '',
  height = 180,
  legend,
  onItemDoubleClick,
  itemHint,
  onSeriesDoubleClick,
  seriesHint,
}: {
  items?: BarItem[];
  groups?: BarGroup[];
  unit?: string;
  height?: number;
  /** Подписи серий для режима groups, напр. [{ key: 'with', label: 'с СНИЛС', color }] */
  legend?: { key: string; label: string; color?: string }[];
  /** Двойной клик по столбцу (режим items). */
  onItemDoubleClick?: (item: BarItem) => void;
  /** Подсказка при наведении на столбец (добавляется к title). */
  itemHint?: string;
  /** Двойной клик по серии в группе (режим groups). */
  onSeriesDoubleClick?: (group: BarGroup, series: BarSeries) => void;
  seriesHint?: string;
}) {
  if (groups && groups.length) {
    const allVals = groups.flatMap((g) => g.series.map((s) => s.value));
    const max = Math.max(...allVals, 1);
    return (
      <div className="bar-chart-wrap">
        {legend && legend.length > 0 && (
          <div className="bar-legend">
            {legend.map((l) => (
              <span key={l.key} className="bar-legend__item">
                <span
                  className="bar-legend__swatch"
                  style={{ background: l.color || 'var(--accent)' }}
                />
                {l.label}
              </span>
            ))}
          </div>
        )}
        <div className="bar-chart bar-chart--grouped" style={{ minHeight: height }}>
          {groups.map((group) => (
            <div className="bar-group" key={group.label} title={group.label}>
              <div className="bar-group__pair">
                {group.series.map((s) => {
                  const seriesClickable = Boolean(onSeriesDoubleClick);
                  const tip = [
                    `${group.label} · ${s.key}: ${fmtValue(s.value)}${unit}`,
                    seriesHint ||
                      (seriesClickable ? 'Двойной клик — список историй этой группы' : ''),
                  ]
                    .filter(Boolean)
                    .join('\n');
                  return (
                    <div
                      className={`bar-group__col${seriesClickable ? ' bar-col--clickable' : ''}`}
                      key={s.key}
                      title={tip}
                      onDoubleClick={
                        onSeriesDoubleClick
                          ? (e) => {
                              e.preventDefault();
                              onSeriesDoubleClick(group, s);
                            }
                          : undefined
                      }
                    >
                      <div className="bar-value">
                        {fmtValue(s.value)}
                        {unit}
                      </div>
                      <div className="bar-track bar-track--slim">
                        <div
                          className="bar-fill"
                          style={{
                            height: `${Math.max(s.value > 0 ? 4 : 0, (s.value / max) * 100)}%`,
                            background: s.color || 'var(--accent)',
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="bar-label">{group.label}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const list = items || [];
  if (!list.length) {
    return <div className="bar-empty">Нет данных для графика</div>;
  }
  const max = Math.max(...list.map((i) => i.value), 1);
  const clickable = Boolean(onItemDoubleClick);
  return (
    <div className="bar-chart" style={{ minHeight: height }}>
      {list.map((item) => {
        const tip = [
          `${item.label}: ${fmtValue(item.value)}${unit}`,
          itemHint || (clickable ? 'Двойной клик — список нарушений этого типа' : ''),
        ]
          .filter(Boolean)
          .join('\n');
        return (
          <div
            className={`bar-col${clickable ? ' bar-col--clickable' : ''}`}
            key={item.label}
            title={tip}
            onDoubleClick={
              onItemDoubleClick
                ? (e) => {
                    e.preventDefault();
                    onItemDoubleClick(item);
                  }
                : undefined
            }
          >
            <div className="bar-value">
              {fmtValue(item.value)}
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
        );
      })}
    </div>
  );
}

import type { SortMode } from '../lib/sortUtils';
import { SORT_MODE_HINTS } from '../lib/sortUtils';
import './SortControls.css';

const MODES: { id: SortMode; label: string }[] = [
  { id: 'alpha', label: 'А→Я' },
  { id: 'asc', label: '↑' },
  { id: 'desc', label: '↓' },
];

export function SortControls({
  mode,
  onChange,
}: {
  mode: SortMode;
  onChange: (mode: SortMode) => void;
}) {
  return (
    <div className="sort-controls" role="group" aria-label="Сортировка">
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          className={`sort-controls__btn${mode === m.id ? ' sort-controls__btn--active' : ''}`}
          title={SORT_MODE_HINTS[m.id]}
          aria-pressed={mode === m.id}
          onClick={() => onChange(m.id)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

import { useMemo, useState } from 'react';
import './SearchableSelect.css';

export type OpItem = { code: string; name: string; group?: string };

export function SearchableMultiSelect({
  items,
  value,
  onChange,
  placeholder = 'Поиск кода или названия…',
}: {
  items: OpItem[];
  value: string[];
  onChange: (codes: string[]) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState('');
  const selected = useMemo(() => new Set(value), [value]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items.slice(0, 80);
    return items
      .filter(
        (it) =>
          it.code.toLowerCase().includes(q) ||
          it.name.toLowerCase().includes(q) ||
          (it.group || '').toLowerCase().includes(q),
      )
      .slice(0, 80);
  }, [items, query]);

  const toggle = (code: string) => {
    if (selected.has(code)) onChange(value.filter((c) => c !== code));
    else onChange([...value, code]);
  };

  return (
    <div className="sms">
      <input
        className="sms-search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
      />
      {value.length > 0 && (
        <div className="sms-chips">
          {value.map((code) => {
            const meta = items.find((i) => i.code === code);
            return (
              <button key={code} type="button" className="sms-chip" onClick={() => toggle(code)}>
                {meta ? `${code} · ${meta.name}` : code} ×
              </button>
            );
          })}
        </div>
      )}
      <div className="sms-list">
        {filtered.map((it) => (
          <label key={it.code} className={`sms-row ${selected.has(it.code) ? 'on' : ''}`}>
            <input
              type="checkbox"
              checked={selected.has(it.code)}
              onChange={() => toggle(it.code)}
            />
            <span className="sms-code">{it.code}</span>
            <span className="sms-name">{it.name}</span>
          </label>
        ))}
        {!filtered.length && <div className="sms-empty">Ничего не найдено</div>}
      </div>
    </div>
  );
}

export function SearchableSingleSelect({
  options,
  value,
  onChange,
  placeholder = 'Поиск…',
  allowCustom = true,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  allowCustom?: boolean;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options.slice(0, 40);
    return options.filter((o) => o.toLowerCase().includes(q)).slice(0, 40);
  }, [options, query]);

  return (
    <div className="sms">
      <input
        className="sms-search"
        value={open ? query : value}
        onFocus={() => {
          setOpen(true);
          setQuery(value);
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          if (allowCustom) onChange(e.target.value);
          setOpen(true);
        }}
        onBlur={() => {
          // delay so click on option works
          window.setTimeout(() => setOpen(false), 150);
        }}
        placeholder={placeholder}
      />
      {open && (
        <div className="sms-list sms-list--popup">
          {filtered.map((opt) => (
            <button
              key={opt}
              type="button"
              className={`sms-option ${opt === value ? 'on' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onChange(opt);
                setQuery(opt);
                setOpen(false);
              }}
            >
              {opt}
            </button>
          ))}
          {!filtered.length && <div className="sms-empty">Нет совпадений</div>}
        </div>
      )}
    </div>
  );
}

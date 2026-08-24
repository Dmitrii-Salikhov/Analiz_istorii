import { useMemo } from 'react';
import './EmkDepartmentScope.css';

export type EmkScopeMode = 'single' | 'summary';
export type EmkSummaryMode = 'all' | 'multi';

export function EmkDepartmentScope({
  departments,
  singleDepartment,
  onSingleDepartmentChange,
  scopeMode,
  onScopeModeChange,
  summaryMode,
  onSummaryModeChange,
  selectedDepartments,
  onSelectedDepartmentsChange,
  disabled,
  onApply,
  radioName = 'emk-summary-mode',
}: {
  departments: string[];
  singleDepartment: string;
  onSingleDepartmentChange: (value: string) => void;
  scopeMode: EmkScopeMode;
  onScopeModeChange: (mode: EmkScopeMode) => void;
  summaryMode: EmkSummaryMode;
  onSummaryModeChange: (mode: EmkSummaryMode) => void;
  selectedDepartments: string[];
  onSelectedDepartmentsChange: (values: string[]) => void;
  disabled?: boolean;
  onApply: () => void;
  /** Уникальное имя radio-группы (если компонент на нескольких вкладках). */
  radioName?: string;
}) {
  const selectedSet = useMemo(() => new Set(selectedDepartments), [selectedDepartments]);
  const allSelected =
    departments.length > 0 && departments.every((name) => selectedSet.has(name));

  const toggleDepartment = (name: string) => {
    if (selectedSet.has(name)) {
      onSelectedDepartmentsChange(selectedDepartments.filter((d) => d !== name));
    } else {
      onSelectedDepartmentsChange([...selectedDepartments, name]);
    }
  };

  const toggleAllDepartments = () => {
    onSelectedDepartmentsChange(allSelected ? [] : [...departments]);
  };

  return (
    <div className="emk-dept-scope">
      <div className="emk-dept-scope__modes" role="tablist" aria-label="Режим анализа по отделениям">
        <button
          type="button"
          className={`emk-dept-scope__mode ${scopeMode === 'single' ? 'active' : ''}`}
          disabled={disabled}
          onClick={() => onScopeModeChange('single')}
        >
          Одно отделение
        </button>
        <button
          type="button"
          className={`emk-dept-scope__mode ${scopeMode === 'summary' ? 'active' : ''}`}
          disabled={disabled}
          onClick={() => onScopeModeChange('summary')}
        >
          Сводка по всем отделениям
        </button>
      </div>

      {scopeMode === 'single' ? (
        <label className="field emk-dept-scope__single" title="Фильтр анализа по отделению госпитализации">
          Отделение
          <select
            value={singleDepartment}
            disabled={disabled || !departments.length}
            onChange={(e) => onSingleDepartmentChange(e.target.value)}
          >
            {departments.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <div className="emk-dept-scope__summary">
          <div className="emk-dept-scope__summary-modes">
            <label className="emk-dept-scope__radio">
              <input
                type="radio"
                name={radioName}
                checked={summaryMode === 'all'}
                disabled={disabled}
                onChange={() => onSummaryModeChange('all')}
              />
              Все отделения ({departments.length})
            </label>
            <label className="emk-dept-scope__radio">
              <input
                type="radio"
                name={radioName}
                checked={summaryMode === 'multi'}
                disabled={disabled}
                onChange={() => onSummaryModeChange('multi')}
              />
              Выбранные отделения
            </label>
          </div>

          {summaryMode === 'multi' && (
            <div className="emk-dept-scope__picker">
              <div className="emk-dept-scope__picker-head">
                <span className="muted">
                  Отмечено: {selectedDepartments.length} из {departments.length}
                </span>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={disabled || !departments.length}
                  onClick={toggleAllDepartments}
                >
                  {allSelected ? 'Снять все' : 'Выбрать все'}
                </button>
              </div>
              <div className="emk-dept-scope__list">
                {departments.map((name) => (
                  <label key={name} className="emk-dept-scope__item">
                    <input
                      type="checkbox"
                      checked={selectedSet.has(name)}
                      disabled={disabled}
                      onChange={() => toggleDepartment(name)}
                    />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <button
            type="button"
            className="btn btn-primary emk-dept-scope__apply"
            disabled={
              disabled ||
              (summaryMode === 'multi' && selectedDepartments.length === 0)
            }
            onClick={onApply}
          >
            Применить сводку
          </button>
        </div>
      )}
    </div>
  );
}

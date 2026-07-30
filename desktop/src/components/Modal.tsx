import type { ReactNode } from 'react';
import './Modal.css';

export function Modal({
  title,
  hint,
  wide,
  children,
  onClose,
}: {
  title: string;
  hint?: string;
  wide?: boolean;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className={`modal${wide ? ' modal--wide' : ''}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal__head">
          <h2>{title}</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            title="Закрыть окно"
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>
        {hint ? <p className="modal__hint">{hint}</p> : null}
        {children}
      </div>
    </div>
  );
}

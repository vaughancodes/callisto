import { ChevronsUpDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export interface DropdownOption {
  value: string;
  label: React.ReactNode;
}

interface DropdownProps {
  value: string;
  onChange: (value: string) => void;
  options: DropdownOption[];
  /** Hidden input name, for use inside an HTML form that reads via FormData. */
  name?: string;
  placeholder?: React.ReactNode;
  className?: string;
  disabled?: boolean;
}

export function Dropdown({
  value,
  onChange,
  options,
  name,
  placeholder = "Select...",
  className = "",
  disabled = false,
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const selected = options.find((o) => o.value === value);

  return (
    <div className={`relative ${className}`} ref={ref}>
      {name && <input type="hidden" name={name} value={value} />}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text hover:border-card-border-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span className="truncate">
          {selected ? (
            selected.label
          ) : (
            <span className="text-page-text-muted">{placeholder}</span>
          )}
        </span>
        <ChevronsUpDown className="w-3.5 h-3.5 text-page-text-muted shrink-0" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 mt-1 bg-card-bg border border-card-border rounded-lg shadow-lg overflow-hidden z-20 max-h-72 overflow-y-auto">
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                o.value === value
                  ? "bg-brand-sky/15 text-brand-sky"
                  : "text-page-text hover:bg-page-hover"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

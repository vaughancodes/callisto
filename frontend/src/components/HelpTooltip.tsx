import { HelpCircle } from "lucide-react";
import { useState, type ReactNode } from "react";

export function HelpTooltip({ children }: { children: ReactNode }) {
  const [show, setShow] = useState(false);

  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <HelpCircle className="w-3.5 h-3.5 text-page-text-muted cursor-help" />
      {show && (
        <span
          role="tooltip"
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 px-3 py-2 bg-page-bg-tertiary text-page-text text-xs rounded-lg border border-card-border shadow-lg z-50 normal-case font-normal"
        >
          {children}
        </span>
      )}
    </span>
  );
}

import { useEffect, useRef, useState, type ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  delay?: number;
  className?: string;
}

export function Tooltip({
  content,
  children,
  delay = 500,
  className = "",
}: TooltipProps) {
  const [show, setShow] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, []);

  const onEnter = () => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setShow(true), delay);
  };

  const onLeave = () => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
    setShow(false);
  };

  return (
    <span
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      {children}
      {show && (
        <span
          role="tooltip"
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 px-2 py-1 whitespace-nowrap bg-page-bg-tertiary text-page-text text-xs rounded-md border border-card-border shadow-lg z-50 normal-case font-normal pointer-events-none"
        >
          {content}
        </span>
      )}
    </span>
  );
}

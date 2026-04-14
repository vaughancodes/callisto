import { Loader2 } from "lucide-react";

export function LoadingSpinner({
  label,
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 py-16 ${className}`}
    >
      <Loader2 className="w-6 h-6 animate-spin text-brand-sky" />
      {label && <p className="text-sm text-page-text-muted">{label}</p>}
    </div>
  );
}

export function PageLoadingSpinner({ label }: { label?: string }) {
  return (
    <div className="p-6">
      <LoadingSpinner label={label} className="min-h-[50vh]" />
    </div>
  );
}

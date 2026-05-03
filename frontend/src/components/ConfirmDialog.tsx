import { AlertTriangle } from "lucide-react";
import { ScrollLock } from "../hooks/useBodyScrollLock";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: React.ReactNode;
  warning?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  warning,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <ScrollLock />
      <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-danger/15 rounded-full">
            <AlertTriangle className="w-5 h-5 text-danger" />
          </div>
          <h3 className="text-lg font-semibold text-page-text">{title}</h3>
        </div>
        <p className="text-sm text-page-text-secondary mb-2">{message}</p>
        {warning ? (
          <p className="text-sm text-danger mb-6">{warning}</p>
        ) : (
          <div className="mb-4" />
        )}
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm bg-danger text-white rounded-lg hover:bg-danger/80"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

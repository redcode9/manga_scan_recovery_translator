/**
 * Toast — minimal global notification system.
 *
 * Why a custom one instead of react-hot-toast / sonner: keeps the
 * dependency graph tight, supports our dark palette out of the box,
 * uses ``aria-live="polite"`` for screen-reader announcement and
 * auto-dismisses without stealing focus (WCAG 4.1.3 / SR rules).
 */

import {
  AlertTriangle,
  CheckCircle2,
  CircleX,
  Info,
  X,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

type ToastTone = "success" | "error" | "info" | "warn";

interface Toast {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
  duration: number;
}

interface ToastApi {
  show: (
    tone: ToastTone,
    title: string,
    options?: { description?: string; duration?: number },
  ) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  warn: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback<ToastApi["show"]>((tone, title, options) => {
    const id = ++idRef.current;
    const duration = options?.duration ?? (tone === "error" ? 6000 : 3500);
    setToasts((prev) => [
      ...prev,
      { id, tone, title, description: options?.description, duration },
    ]);
  }, []);

  const api: ToastApi = {
    show,
    success: (title, description) => show("success", title, { description }),
    error: (title, description) => show("error", title, { description }),
    info: (title, description) => show("info", title, { description }),
    warn: (title, description) => show("warn", title, { description }),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[1000] flex w-full max-w-sm flex-col gap-2"
        role="region"
        aria-live="polite"
        aria-label="Notifiche"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: () => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, toast.duration);
    return () => window.clearTimeout(timer);
  }, [toast.duration, onDismiss]);

  const palette = {
    success: {
      ring: "ring-emerald-500/30",
      bg: "bg-emerald-500/10",
      text: "text-emerald-100",
      icon: <CheckCircle2 size={16} className="text-emerald-300" />,
    },
    error: {
      ring: "ring-rose-500/30",
      bg: "bg-rose-500/10",
      text: "text-rose-100",
      icon: <CircleX size={16} className="text-rose-300" />,
    },
    warn: {
      ring: "ring-amber-500/30",
      bg: "bg-amber-500/10",
      text: "text-amber-100",
      icon: <AlertTriangle size={16} className="text-amber-300" />,
    },
    info: {
      ring: "ring-sky-500/30",
      bg: "bg-sky-500/10",
      text: "text-sky-100",
      icon: <Info size={16} className="text-sky-300" />,
    },
  }[toast.tone];

  return (
    <div
      role={toast.tone === "error" || toast.tone === "warn" ? "alert" : "status"}
      className={`msrt-toast pointer-events-auto flex items-start gap-3 rounded-xl px-4 py-3 shadow-lg ring-1 backdrop-blur-md ${palette.ring} ${palette.bg} ${palette.text}`}
    >
      <span className="mt-0.5 shrink-0">{palette.icon}</span>
      <div className="flex-1 text-sm">
        <p className="font-medium">{toast.title}</p>
        {toast.description && (
          <p className="mt-0.5 text-xs opacity-80">{toast.description}</p>
        )}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Chiudi notifica"
        className="rounded-md p-1 text-current opacity-70 transition hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
      >
        <X size={14} />
      </button>
    </div>
  );
}

import qrcode from "qrcode-generator";
import { Check } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { cn } from "./primitives";

/* ---------------------------------------------------------------- Order code
   YYMMDD-NNNNN-C: date muted, serial bold, check digit as a small brand chip. */

export function formatOrderCode(code: string): string {
  const d = code.replace(/\D/g, "");
  if (d.length < 12) return code;
  return `${d.slice(0, 6)}-${d.slice(6, 11)}-${d.slice(11, 12)}`;
}

export function OrderCode({
  code,
  size = "md",
  className,
  tone = "default",
}: {
  code: string;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  tone?: "default" | "inverse";
}) {
  const d = code.replace(/\D/g, "");
  const text = {
    sm: "text-[13px]",
    md: "text-[15px]",
    lg: "text-[22px]",
    xl: "text-[34px] tracking-[-0.01em]",
  }[size];
  if (d.length < 12) return <span className={cn("font-mono", text, className)}>{code}</span>;
  const inverse = tone === "inverse";
  return (
    <span
      className={cn("inline-flex items-baseline font-mono font-semibold tabular", text, className)}
      aria-label={formatOrderCode(d)}
      translate="no"
    >
      <span className={inverse ? "text-white/60" : "text-sand-500"}>{d.slice(0, 6)}</span>
      <span className={inverse ? "text-white/40" : "text-sand-300"}>-</span>
      <span className={inverse ? "text-white" : "text-ink"}>{d.slice(6, 11)}</span>
      <span className={inverse ? "text-white/40" : "text-sand-300"}>-</span>
      <span
        className={cn(
          "rounded-[0.3em] px-[0.28em]",
          inverse ? "bg-white/15 text-white" : "bg-brand-50 text-brand-700",
        )}
      >
        {d.slice(11, 12)}
      </span>
    </span>
  );
}

/* ---------------------------------------------------------------- QR code (SVG, no network) */

export function QrCode({
  value,
  size = 160,
  className,
  label,
}: {
  value: string;
  size?: number;
  className?: string;
  label?: string;
}) {
  const path = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(value);
    qr.make();
    const n = qr.getModuleCount();
    let d = "";
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        if (qr.isDark(r, c)) d += `M${c + 2},${r + 2}h1v1h-1z`;
      }
    }
    return { d, n: n + 4 };
  }, [value]);
  return (
    <svg
      viewBox={`0 0 ${path.n} ${path.n}`}
      width={size}
      height={size}
      className={cn("rounded-lg bg-white", className)}
      role="img"
      aria-label={label ?? value}
      shapeRendering="crispEdges"
    >
      <rect width={path.n} height={path.n} fill="#fff" />
      <path d={path.d} fill="#13201b" />
    </svg>
  );
}

/* ---------------------------------------------------------------- Progress timeline */

export type TimelineStep = {
  key: string;
  title: ReactNode;
  detail?: ReactNode;
  state: "done" | "current" | "pending" | "error";
  at?: ReactNode;
};

export function Timeline({ steps, className }: { steps: TimelineStep[]; className?: string }) {
  return (
    <ol className={cn("relative", className)}>
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        return (
          <li key={s.key} className="relative flex gap-3.5 pb-5 last:pb-0">
            {!last && (
              <span
                className={cn(
                  "absolute left-[13px] top-7 h-[calc(100%-1.5rem)] w-0.5 rounded-full",
                  s.state === "done" ? "bg-brand-400" : "bg-sand-200",
                )}
              />
            )}
            <span
              className={cn(
                "relative z-10 grid size-7 shrink-0 place-items-center rounded-full text-[12px] font-bold",
                s.state === "done" && "bg-brand-600 text-white",
                s.state === "current" && "bg-white text-brand-700 ring-2 ring-brand-500 animate-pulse-ring",
                s.state === "pending" && "bg-sand-100 text-sand-400 ring-1 ring-sand-200",
                s.state === "error" && "bg-danger-600 text-white",
              )}
            >
              {s.state === "done" ? <Check className="size-4" strokeWidth={3} /> : i + 1}
            </span>
            <div className="min-w-0 pt-0.5">
              <div
                className={cn(
                  "text-[15px] font-semibold leading-snug",
                  s.state === "pending" ? "text-sand-400" : "text-ink",
                  s.state === "error" && "text-danger-700",
                )}
              >
                {s.title}
              </div>
              {s.detail && <div className="mt-0.5 text-[13px] leading-relaxed text-sand-600">{s.detail}</div>}
              {s.at && <div className="mt-0.5 text-[12px] text-sand-400">{s.at}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* ---------------------------------------------------------------- Countdown */

export function useCountdown(until: string | Date | null | undefined): number {
  const target = until ? new Date(until).getTime() : 0;
  const [left, setLeft] = useState(() => Math.max(0, target - Date.now()));
  useEffect(() => {
    if (!target) return;
    setLeft(Math.max(0, target - Date.now()));
    const id = window.setInterval(() => setLeft(Math.max(0, target - Date.now())), 1000);
    return () => window.clearInterval(id);
  }, [target]);
  return left;
}

export function formatDuration(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/* ---------------------------------------------------------------- Brand mark */

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-9", className)} aria-hidden>
      <defs>
        <linearGradient id="bmu-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1d8763" />
          <stop offset="1" stopColor="#04211a" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#bmu-g)" />
      <path d="M20 8.5c4.6 6 7.4 10.3 7.4 14.2a7.4 7.4 0 1 1-14.8 0c0-3.9 2.8-8.2 7.4-14.2Z" fill="#fff" />
      <circle cx="20" cy="23" r="3.1" fill="#e8364a" />
      <path d="M16.6 21.2a4 4 0 0 1 2.2-2.6" stroke="#1d8763" strokeWidth="1.4" strokeLinecap="round" fill="none" />
    </svg>
  );
}

export function Logo({ className, subtitle }: { className?: string; subtitle?: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="leading-none">
        <span className="block text-[17px] font-bold tracking-[-0.02em]">
          BMU <span className="font-semibold text-brand-600">Lab</span>
        </span>
        {subtitle && <span className="mt-1 block text-[11px] font-medium text-sand-500">{subtitle}</span>}
      </span>
    </span>
  );
}

/* ---------------------------------------------------------------- Live dot */

export function LiveDot({ tone = "brand", className }: { tone?: "brand" | "warn" | "danger"; className?: string }) {
  const c = { brand: "bg-brand-500", warn: "bg-warn-600", danger: "bg-danger-600" }[tone];
  return (
    <span className={cn("relative inline-flex size-2.5", className)}>
      <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-60", c)} />
      <span className={cn("relative inline-flex size-2.5 rounded-full", c)} />
    </span>
  );
}

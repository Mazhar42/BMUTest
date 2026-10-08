import { clsx, type ClassValue } from "clsx";
import { Loader2 } from "lucide-react";
import {
  forwardRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type LabelHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TdHTMLAttributes,
  type TextareaHTMLAttributes,
  type ThHTMLAttributes,
} from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/* ---------------------------------------------------------------- Button */

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "subtle" | "dark";
export type ButtonSize = "sm" | "md" | "lg" | "xl";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.15),0_1px_2px_rgb(4_33_26/0.3)] hover:bg-brand-700 active:bg-brand-800",
  secondary: "bg-brand-50 text-brand-800 hover:bg-brand-100 active:bg-brand-200",
  outline: "border border-sand-300 bg-white text-ink hover:bg-sand-50 hover:border-sand-400",
  ghost: "text-sand-700 hover:bg-sand-100 hover:text-ink",
  danger: "bg-danger-600 text-white hover:bg-danger-700",
  subtle: "bg-sand-100 text-sand-800 hover:bg-sand-200",
  dark: "bg-ink text-white hover:bg-brand-950",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-xl",
  lg: "h-12 px-5 text-[15px] gap-2 rounded-xl",
  xl: "h-14 px-6 text-base gap-2.5 rounded-2xl",
};

export function buttonClass(variant: ButtonVariant = "primary", size: ButtonSize = "md", extra?: string): string {
  return cn(
    "inline-flex select-none items-center justify-center font-semibold tracking-[-0.005em] whitespace-nowrap",
    "transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:scale-[0.985]",
    "disabled:pointer-events-none disabled:opacity-50",
    variants[variant],
    sizes[size],
    extra,
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
  iconRight?: ReactNode;
  block?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, iconRight, block, className, children, disabled, type, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      disabled={disabled || loading}
      className={buttonClass(variant, size, cn(block && "w-full", className))}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
      {iconRight}
    </button>
  );
});

/* ---------------------------------------------------------------- Card */

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-2xl border border-sand-200/80 bg-white shadow-card", className)} {...rest} />;
}

export function CardHeader({
  title,
  subtitle,
  action,
  icon,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start gap-3 border-b border-sand-100 px-5 py-4", className)}>
      {icon && (
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700">{icon}</div>
      )}
      <div className="min-w-0 flex-1">
        <h3 className="text-[15px] font-semibold leading-tight text-ink">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[13px] text-sand-600">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4", className)} {...rest} />;
}

export function CardFooter({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center justify-end gap-2 rounded-b-2xl border-t border-sand-100 bg-sand-50/60 px-5 py-3", className)}
      {...rest}
    />
  );
}

/* ---------------------------------------------------------------- Form controls */

const control =
  "w-full rounded-xl border border-sand-300 bg-white px-3.5 text-[15px] text-ink placeholder:text-sand-400 " +
  "transition-[border-color,box-shadow] outline-none focus:border-brand-500 focus:shadow-glow " +
  "disabled:cursor-not-allowed disabled:bg-sand-50 disabled:text-sand-500 aria-[invalid=true]:border-danger-600";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { inputSize?: "md" | "lg" | "xl" }>(
  function Input({ className, inputSize = "md", ...rest }, ref) {
    const h = inputSize === "xl" ? "h-16 text-2xl" : inputSize === "lg" ? "h-12 text-base" : "h-10";
    return <input ref={ref} className={cn(control, h, className)} {...rest} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, ...rest },
  ref,
) {
  return <textarea ref={ref} className={cn(control, "min-h-24 py-2.5", className)} {...rest} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn(
        control,
        "h-10 appearance-none bg-[length:16px] bg-[right_0.75rem_center] bg-no-repeat pr-9",
        "bg-[url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238a7d66' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")]",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
});

export function Label({ className, ...rest }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("mb-1.5 block text-[13px] font-semibold text-sand-800", className)} {...rest} />;
}

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
  className,
  required,
}: {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
  required?: boolean;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      {label && (
        <Label htmlFor={htmlFor}>
          {label}
          {required && <span className="ml-0.5 text-accent-600">*</span>}
        </Label>
      )}
      {children}
      {error ? (
        <p className="mt-1.5 text-[13px] font-medium text-danger-600" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1.5 text-[13px] text-sand-500">{hint}</p>
      ) : null}
    </div>
  );
}

export function Checkbox({
  label,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return (
    <label className={cn("inline-flex cursor-pointer items-center gap-2.5 text-sm text-ink", className)}>
      <input
        type="checkbox"
        className="size-[18px] rounded-md border-sand-300 accent-brand-600"
        {...rest}
      />
      {label}
    </label>
  );
}

/* ---------------------------------------------------------------- Feedback */

export type Tone = "neutral" | "brand" | "ok" | "warn" | "danger" | "info" | "violet" | "dark";

const tones: Record<Tone, string> = {
  neutral: "bg-sand-100 text-sand-700 ring-sand-200",
  brand: "bg-brand-50 text-brand-700 ring-brand-200",
  ok: "bg-ok-50 text-ok-600 ring-brand-200",
  warn: "bg-warn-50 text-warn-700 ring-warn-100",
  danger: "bg-danger-50 text-danger-700 ring-danger-100",
  info: "bg-info-50 text-info-700 ring-info-100",
  violet: "bg-violet-50 text-violet-600 ring-violet-50",
  dark: "bg-ink text-white ring-ink",
};

export function Badge({
  tone = "neutral",
  dot,
  className,
  children,
}: {
  tone?: Tone;
  dot?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[12px] font-semibold ring-1 ring-inset",
        tones[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current opacity-80" />}
      {children}
    </span>
  );
}

export function Callout({
  tone = "info",
  title,
  icon,
  children,
  className,
}: {
  tone?: Tone;
  title?: ReactNode;
  icon?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex gap-3 rounded-xl px-4 py-3 ring-1 ring-inset", tones[tone], className)} role="status">
      {icon && <div className="mt-0.5 shrink-0">{icon}</div>}
      <div className="min-w-0 text-[14px] leading-relaxed">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={cn(title && "mt-0.5 opacity-90")}>{children}</div>}
      </div>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-5 animate-spin text-brand-600", className)} aria-label="loading" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-sand-200/70", className)} />;
}

export function EmptyState({
  icon,
  title,
  body,
  action,
  className,
}: {
  icon?: ReactNode;
  title: ReactNode;
  body?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-12 text-center", className)}>
      {icon && (
        <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-600 ring-8 ring-brand-50/50">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {body && <p className="mt-1 max-w-sm text-sm text-sand-600">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  eyebrow,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-6 flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-brand-600">{eyebrow}</div>}
        <h1 className="text-[26px] font-bold leading-tight tracking-[-0.02em] text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-[14px] text-sand-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-md border border-sand-300 bg-white px-1.5 py-0.5 font-mono text-[11px] font-semibold text-sand-600 shadow-[0_1px_0_var(--color-sand-300)]">
      {children}
    </kbd>
  );
}

export function Divider({ label, className }: { label?: ReactNode; className?: string }) {
  if (!label) return <hr className={cn("border-sand-200", className)} />;
  return (
    <div className={cn("flex items-center gap-3 text-[12px] font-semibold uppercase tracking-wider text-sand-400", className)}>
      <span className="h-px flex-1 bg-sand-200" />
      {label}
      <span className="h-px flex-1 bg-sand-200" />
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon,
  tone = "brand",
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-[13px] font-medium text-sand-600">{label}</div>
        {icon && <div className={cn("grid size-8 place-items-center rounded-lg ring-1 ring-inset", tones[tone])}>{icon}</div>}
      </div>
      <div className="mt-2 text-[28px] font-bold leading-none tracking-[-0.02em] text-ink tabular">{value}</div>
      {hint && <div className="mt-1.5 text-[12px] text-sand-500">{hint}</div>}
    </Card>
  );
}

export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  className,
  size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode }[];
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <div className={cn("inline-flex rounded-xl bg-sand-100 p-1 ring-1 ring-inset ring-sand-200", className)} role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-lg font-semibold transition-all",
            size === "sm" ? "px-2.5 py-1 text-[12px]" : "px-3.5 py-1.5 text-[13px]",
            o.value === value ? "bg-white text-ink shadow-sm" : "text-sand-600 hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- Table */

export function Table({ className, ...rest }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <table className={cn("w-full border-collapse text-left text-[14px]", className)} {...rest} />
    </div>
  );
}

export function TH({ className, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "border-b border-sand-200 bg-sand-50/70 px-4 py-2.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-sand-500 first:pl-5 last:pr-5",
        className,
      )}
      {...rest}
    />
  );
}

export function TD({ className, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("border-b border-sand-100 px-4 py-3 align-middle first:pl-5 last:pr-5", className)} {...rest} />;
}

export function TR({ className, ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("transition-colors hover:bg-brand-50/30", className)} {...rest} />;
}

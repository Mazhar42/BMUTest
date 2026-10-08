import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "./primitives";

/* ---------------------------------------------------------------- Dialog */

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = "md",
  tone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  tone?: "danger";
}) {
  const width = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-5xl" }[size];
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-[2px] animate-fade-in" />
        <DialogPrimitive.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-h-[92dvh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-hidden",
            "flex flex-col rounded-2xl bg-white shadow-lift animate-slide-up focus:outline-none",
            width,
          )}
        >
          <div
            className={cn(
              "flex items-start gap-3 border-b px-5 py-4",
              tone === "danger" ? "border-danger-100 bg-danger-50" : "border-sand-100",
            )}
          >
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="text-[16px] font-semibold text-ink">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="mt-0.5 text-[13px] text-sand-600">
                  {description}
                </DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close
              className="-mr-1 grid size-8 place-items-center rounded-lg text-sand-500 hover:bg-sand-100 hover:text-ink"
              aria-label="Close"
            >
              <X className="size-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 scrollbar-thin">{children}</div>
          {footer && (
            <div className="flex items-center justify-end gap-2 border-t border-sand-100 bg-sand-50/60 px-5 py-3">
              {footer}
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/* ---------------------------------------------------------------- Tabs */

export function Tabs({
  value,
  onValueChange,
  tabs,
  className,
}: {
  value: string;
  onValueChange: (v: string) => void;
  tabs: { value: string; label: ReactNode; content: ReactNode; count?: number }[];
  className?: string;
}) {
  return (
    <TabsPrimitive.Root value={value} onValueChange={onValueChange} className={className}>
      <TabsPrimitive.List className="mb-4 flex gap-1 overflow-x-auto border-b border-sand-200 scrollbar-thin">
        {tabs.map((t) => (
          <TabsPrimitive.Trigger
            key={t.value}
            value={t.value}
            className={cn(
              "-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-3.5 py-2.5 text-[14px] font-semibold text-sand-500",
              "transition-colors hover:text-ink data-[state=active]:border-brand-600 data-[state=active]:text-brand-700",
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="rounded-full bg-sand-100 px-1.5 text-[11px] text-sand-600 tabular">{t.count}</span>
            )}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {tabs.map((t) => (
        <TabsPrimitive.Content key={t.value} value={t.value} className="focus:outline-none">
          {t.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}

/* ---------------------------------------------------------------- Switch */

export function Switch({
  checked,
  onCheckedChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  label?: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      {(label || description) && (
        <span className="min-w-0">
          {label && <span className="block text-[14px] font-semibold text-ink">{label}</span>}
          {description && <span className="mt-0.5 block text-[13px] text-sand-600">{description}</span>}
        </span>
      )}
      <SwitchPrimitive.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className="relative h-6 w-11 shrink-0 rounded-full bg-sand-300 transition-colors data-[state=checked]:bg-brand-600 disabled:opacity-50"
      >
        <SwitchPrimitive.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
      </SwitchPrimitive.Root>
    </label>
  );
}

/* ---------------------------------------------------------------- Dropdown */

export function Dropdown({
  trigger,
  items,
  align = "end",
}: {
  trigger: ReactNode;
  items: ({ label: ReactNode; icon?: ReactNode; onSelect: () => void; danger?: boolean } | "separator")[];
  align?: "start" | "end";
}) {
  return (
    <DropdownPrimitive.Root>
      <DropdownPrimitive.Trigger asChild>{trigger}</DropdownPrimitive.Trigger>
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content
          align={align}
          sideOffset={6}
          className="z-50 min-w-48 rounded-xl border border-sand-200 bg-white p-1 shadow-lift animate-fade-in"
        >
          {items.map((item, i) =>
            item === "separator" ? (
              <DropdownPrimitive.Separator key={i} className="my-1 h-px bg-sand-100" />
            ) : (
              <DropdownPrimitive.Item
                key={i}
                onSelect={item.onSelect}
                className={cn(
                  "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-[14px] outline-none",
                  item.danger ? "text-danger-600 data-[highlighted]:bg-danger-50" : "text-ink data-[highlighted]:bg-sand-100",
                )}
              >
                {item.icon && <span className="text-sand-500">{item.icon}</span>}
                {item.label}
              </DropdownPrimitive.Item>
            ),
          )}
        </DropdownPrimitive.Content>
      </DropdownPrimitive.Portal>
    </DropdownPrimitive.Root>
  );
}

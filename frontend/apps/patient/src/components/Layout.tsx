import { unwrap } from "@bmu/api-client";
import { setLanguage, useI18n, type Lang } from "@bmu/i18n";
import { cn, LogoMark, SegmentedControl } from "@bmu/ui";
import { ArrowLeft, WifiOff } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { api, hasSession } from "../lib/api";

const WELCOME_KEY = "bmu.welcomed";

export function welcomed(): boolean {
  try {
    return window.localStorage.getItem(WELCOME_KEY) === "1";
  } catch {
    return true;
  }
}

export function markWelcomed(): void {
  try {
    window.localStorage.setItem(WELCOME_KEY, "1");
  } catch {
    /* ignore */
  }
}

/** Switch language locally and remember it on the account (for SMS) when signed in. */
export function changeLanguage(lang: Lang): void {
  setLanguage(lang);
  if (hasSession()) void unwrap(api.PATCH("/api/v1/patient/me", { body: { preferred_language: lang } })).catch(() => {});
}

export function LanguageToggle({ className }: { className?: string }) {
  const { lang } = useI18n();
  return (
    <SegmentedControl
      size="sm"
      className={className}
      value={lang}
      onChange={changeLanguage}
      options={[
        { value: "bn", label: "বাংলা" },
        { value: "en", label: "EN" },
      ]}
    />
  );
}

function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

/** Mobile-first page: large tap targets, readable at 360 px. */
export function Screen({
  title,
  back,
  children,
  footer,
  className,
}: {
  title?: ReactNode;
  back?: string | true;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const online = useOnline();
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col bg-paper paper-grain">
      <header className="sticky top-0 z-20 flex h-14 items-center gap-2 bg-paper/90 px-3 backdrop-blur-md">
        {back ? (
          <button
            type="button"
            aria-label={t("common.back")}
            onClick={() => (back === true ? navigate(-1) : navigate(back))}
            className="grid size-10 place-items-center rounded-xl text-ink hover:bg-sand-100"
          >
            <ArrowLeft className="size-5" />
          </button>
        ) : (
          <LogoMark className="ml-1 size-8" />
        )}
        <h1 className="min-w-0 flex-1 truncate text-[17px] font-bold">{title}</h1>
        <LanguageToggle />
      </header>
      {!online && (
        <div className="mx-4 mb-2 flex items-center gap-2 rounded-xl bg-warn-50 px-3 py-2 text-[13px] text-warn-700">
          <WifiOff className="size-4" /> {t("common.offline")}
        </div>
      )}
      <main className={cn("flex-1 px-4 pb-6", className)}>{children}</main>
      {footer && (
        <footer className="sticky bottom-0 border-t border-sand-200 bg-paper/95 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur">
          {footer}
        </footer>
      )}
    </div>
  );
}

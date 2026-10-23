import { unwrap } from "@bmu/api-client";
import { formatTime, setLanguage, useI18n, type Lang } from "@bmu/i18n";
import { Badge, Button, cn, Dropdown, Field, Input, LiveDot, Logo, LogoMark, SegmentedControl } from "@bmu/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Hash, KeyRound, Lock, LogOut, Menu, MonitorSmartphone, ScanBarcode, Search, X } from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { api, tokenStore } from "../lib/api";
import { useErrorToast } from "../lib/errors";
import { classifyScan, useScanner } from "../lib/scanner";
import { useSession } from "../lib/session";
import { ChangePasswordDialog, PinDialog } from "../pages/AccountDialogs";
import { NAV } from "./nav";

export function Shell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { can } = useSession();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => can(...i.perms)) })).filter((g) => g.items.length);

  const sidebar = (
    <nav className="flex h-full flex-col bg-brand-950 text-white">
      <div className="flex h-16 items-center gap-2.5 px-5">
        <LogoMark className="size-8" />
        <div className="leading-none">
          <div className="text-[15px] font-bold tracking-tight">
            BMU <span className="text-brand-300">Lab</span>
          </div>
          <div className="mt-1 text-[10.5px] font-medium uppercase tracking-[0.14em] text-white/45">{t("nav.staffConsole")}</div>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4 scrollbar-thin">
        {groups.map((g) => (
          <div key={g.key} className="mt-4 first:mt-1">
            <div className="px-3 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-white/35">
              {t(`nav.groups.${g.key}`)}
            </div>
            {g.items.map((item) => (
              <NavLink
                key={item.key}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  cn(
                    "group relative mb-0.5 flex items-center gap-3 rounded-xl px-3 py-2 text-[14px] font-medium transition-colors",
                    isActive ? "bg-white/[0.09] text-white" : "text-white/65 hover:bg-white/[0.05] hover:text-white",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && <span className="absolute left-0 top-2 h-5 w-[3px] rounded-r-full bg-brand-300" />}
                    <item.icon className={cn("size-[18px]", isActive ? "text-brand-300" : "text-white/45 group-hover:text-white/70")} />
                    {t(`nav.items.${item.key}`)}
                    {item.milestone && (
                      <span className="ml-auto rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-semibold text-white/40">
                        M{item.milestone}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </div>
      <UserCard />
    </nav>
  );

  return (
    <div className="min-h-dvh bg-paper">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 animate-slide-up">{sidebar}</aside>
          <button className="absolute right-4 top-4 rounded-lg bg-white p-2" onClick={() => setOpen(false)} aria-label="Close menu">
            <X className="size-5" />
          </button>
        </div>
      )}
      <div className="lg:pl-64">
        <TopBar onMenu={() => setOpen(true)} />
        <main className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

function TopBar({ onMenu }: { onMenu: () => void }) {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { me } = useSession();
  const [q, setQ] = useState("");
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 15_000);
    return () => window.clearInterval(id);
  }, []);

  const prefs = useMutation({
    mutationFn: (l: Lang) => unwrap(api.PATCH("/api/v1/staff/auth/me/preferences", { body: { preferred_language: l } })),
    onSuccess: (data) => qc.setQueryData(["me"], data),
  });

  function go(value: string) {
    const scan = classifyScan(value);
    if (scan.kind === "order" || scan.kind === "accession") navigate(`/orders/${scan.value.slice(0, 12)}`);
    else if (value.trim()) navigate(`/patients?q=${encodeURIComponent(value.trim())}`);
  }

  // A scan anywhere (outside dedicated scan fields) opens the order.
  useScanner((v) => go(v), { enabled: !!me });

  function submit(e: FormEvent) {
    e.preventDefault();
    go(q);
    setQ("");
  }

  return (
    <header className="sticky top-0 z-20 border-b border-sand-200/80 bg-paper/85 backdrop-blur-md no-print">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <button className="rounded-lg p-2 hover:bg-sand-100 lg:hidden" onClick={onMenu} aria-label="Menu">
          <Menu className="size-5" />
        </button>
        <form onSubmit={submit} className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-sand-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("nav.globalSearch")}
            className="h-10 w-full rounded-xl border border-sand-200 bg-white pl-10 pr-3 text-[14px] outline-none transition focus:border-brand-500 focus:shadow-glow"
          />
        </form>
        <div className="ml-auto flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-full bg-white px-3 py-1.5 text-[12.5px] font-medium text-sand-600 ring-1 ring-sand-200 md:flex">
            <ScanBarcode className="size-4 text-brand-600" />
            {t("nav.scannerReady")}
            <LiveDot />
          </div>
          <div className="hidden text-[13px] font-semibold text-sand-600 tabular sm:block">{formatTime(now, lang)}</div>
          <SegmentedControl
            size="sm"
            value={lang}
            onChange={(l) => {
              setLanguage(l);
              prefs.mutate(l);
            }}
            options={[
              { value: "en", label: "EN" },
              { value: "bn", label: "বাং" },
            ]}
          />
        </div>
      </div>
    </header>
  );
}

function UserCard() {
  const { t } = useI18n();
  const { me, signOut, setLocked } = useSession();
  const [dialog, setDialog] = useState<"password" | "pin" | null>(null);
  const lock = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/staff/auth/lock")),
    onSuccess: () => setLocked(true),
  });
  if (!me) return null;
  const initials = me.full_name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("");
  return (
    <div className="border-t border-white/10 p-3">
      <Dropdown
        align="start"
        trigger={
          <button className="flex w-full items-center gap-3 rounded-xl p-2 text-left transition hover:bg-white/[0.06]">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 text-[13px] font-bold">
              {initials}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13.5px] font-semibold">{me.full_name}</span>
              <span className="flex items-center gap-1 truncate text-[11.5px] text-white/50">
                <MonitorSmartphone className="size-3" />
                {me.station || t("nav.noStation")}
              </span>
            </span>
          </button>
        }
        items={[
          { label: t("auth.lockNow"), icon: <Lock className="size-4" />, onSelect: () => lock.mutate() },
          { label: t("staff.account.changePassword"), icon: <KeyRound className="size-4" />, onSelect: () => setDialog("password") },
          {
            label: me.has_pin ? t("staff.account.changePin") : t("staff.account.setPin"),
            icon: <Hash className="size-4" />,
            onSelect: () => setDialog("pin"),
          },
          "separator",
          { label: t("common.logout"), icon: <LogOut className="size-4" />, onSelect: () => void signOut(), danger: true },
        ]}
      />
      <div className="mt-1 flex flex-wrap gap-1 px-2">
        {me.roles.map((r) => (
          <span key={`${r.role}-${r.department_id ?? ""}`} className="rounded-md bg-white/[0.07] px-1.5 py-0.5 text-[10.5px] font-semibold text-white/60">
            {t(`roles.${r.role}`)}
          </span>
        ))}
      </div>
      <ChangePasswordDialog open={dialog === "password"} onOpenChange={(v) => setDialog(v ? "password" : null)} />
      <PinDialog open={dialog === "pin"} onOpenChange={(v) => setDialog(v ? "pin" : null)} />
    </div>
  );
}

export function LockScreen() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { me, setLocked, signOut } = useSession();
  const [secret, setSecret] = useState("");
  const onError = useErrorToast();
  const unlock = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/staff/auth/unlock", { body: { secret } })),
    onSuccess: (data) => {
      qc.setQueryData(["me"], data);
      setLocked(false);
      setSecret("");
      void qc.invalidateQueries();
    },
    onError,
  });
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-brand-950/80 p-4 backdrop-blur-md animate-fade-in">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          unlock.mutate();
        }}
        className="w-full max-w-sm rounded-3xl bg-white p-7 shadow-lift animate-slide-up"
      >
        <div className="mb-5 flex flex-col items-center text-center">
          <div className="mb-3 grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-700">
            <Lock className="size-6" />
          </div>
          <h2 className="text-lg font-bold">{t("auth.lockedTitle")}</h2>
          <p className="mt-1 text-[13.5px] text-sand-600">{t("auth.lockedSubtitle")}</p>
          {me && <Badge className="mt-3">{me.full_name}</Badge>}
        </div>
        <Field label={t("auth.passwordOrPin")}>
          <Input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} autoFocus inputSize="lg" />
        </Field>
        <Button type="submit" block size="lg" className="mt-4" loading={unlock.isPending} disabled={!secret}>
          {t("auth.unlock")}
        </Button>
        <button
          type="button"
          className="mt-3 w-full text-center text-[13px] font-semibold text-sand-500 hover:text-ink"
          onClick={() => {
            tokenStore.set(null);
            void signOut();
          }}
        >
          {t("auth.signOutInstead")}
        </button>
      </form>
    </div>
  );
}

export function FullPageSpinner() {
  return (
    <div className="grid min-h-dvh place-items-center bg-paper">
      <Logo />
    </div>
  );
}

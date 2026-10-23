import { unwrap } from "@bmu/api-client";
import { useI18n } from "@bmu/i18n";
import { Button, Callout, Dialog, Field, Input, Logo, toast } from "@bmu/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { errorMessage, useErrorToast } from "../lib/errors";
import { useSession } from "../lib/session";

function PasswordForm({ onDone, submitLabel }: { onDone: () => void; submitLabel: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/staff/auth/me/password", { body: { current_password: current, new_password: next } })),
    onSuccess: async () => {
      toast.success(t("staff.account.passwordChanged"));
      await qc.invalidateQueries({ queryKey: ["me"] });
      onDone();
    },
    onError: (e) => setError(errorMessage(t, e)),
  });
  const mismatch = repeat.length > 0 && repeat !== next;
  function submit(e: FormEvent) {
    e.preventDefault();
    if (next.length >= 10 && !mismatch) change.mutate();
  }
  return (
    <form id="password-form" onSubmit={submit} className="space-y-4">
      <Field label={t("staff.account.currentPassword")}>
        <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus />
      </Field>
      <Field label={t("staff.admin.newPassword")} hint={t("staff.account.passwordRule")}>
        <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
      </Field>
      <Field label={t("staff.account.repeatPassword")} error={mismatch ? t("staff.account.mismatch") : undefined}>
        <Input type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} />
      </Field>
      {error && <Callout tone="danger">{error}</Callout>}
      <Button type="submit" block size="lg" loading={change.isPending} disabled={!current || next.length < 10 || next !== repeat}>
        {submitLabel}
      </Button>
    </form>
  );
}

/** Shown instead of the app when an admin created or reset the account (must_change_password). */
export function ForcePasswordChange() {
  const { t } = useI18n();
  const { me, signOut } = useSession();
  return (
    <div className="grid min-h-dvh place-items-center bg-paper paper-grain p-4">
      <div className="w-full max-w-md rounded-3xl bg-white p-7 shadow-lift">
        <Logo />
        <div className="mt-6 mb-5 flex items-start gap-3">
          <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-700">
            <KeyRound className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold">{t("staff.account.forceTitle")}</h1>
            <p className="mt-1 text-[14px] text-sand-600">{t("staff.account.forceBody", { name: me?.full_name ?? "" })}</p>
          </div>
        </div>
        <PasswordForm onDone={() => undefined} submitLabel={t("staff.account.changePassword")} />
        <button type="button" className="mt-4 w-full text-center text-[13px] font-semibold text-sand-500 hover:text-ink" onClick={() => void signOut()}>
          {t("common.logout")}
        </button>
      </div>
    </div>
  );
}

export function ChangePasswordDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { t } = useI18n();
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={t("staff.account.changePassword")}>
      {open && <PasswordForm onDone={() => onOpenChange(false)} submitLabel={t("common.save")} />}
    </Dialog>
  );
}

/** A 4–6 digit PIN unlocks the idle lock screen faster than the password. */
export function PinDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const save = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/staff/auth/me/pin", { body: { password, pin } })),
    onSuccess: () => {
      toast.success(t("staff.account.pinSaved"));
      void qc.invalidateQueries({ queryKey: ["me"] });
      setPassword("");
      setPin("");
      onOpenChange(false);
    },
    onError,
  });
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("staff.account.setPin")}
      description={t("staff.account.pinHint")}
      footer={
        <Button loading={save.isPending} disabled={!password || !/^\d{4,6}$/.test(pin)} onClick={() => save.mutate()}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="space-y-4">
        <Field label={t("auth.password")}>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
        </Field>
        <Field label={t("staff.account.pin")}>
          <Input
            inputMode="numeric"
            maxLength={6}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
            className="font-mono tracking-[0.4em]"
          />
        </Field>
      </div>
    </Dialog>
  );
}

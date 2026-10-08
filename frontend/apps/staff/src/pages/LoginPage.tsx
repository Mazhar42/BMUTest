import { unwrap, type Schemas } from "@bmu/api-client";
import { setLanguage, useI18n } from "@bmu/i18n";
import { Button, Callout, Field, Input, Logo, QrCode, SegmentedControl } from "@bmu/ui";
import { useMutation } from "@tanstack/react-query";
import { KeyRound, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { errorMessage } from "../lib/errors";
import { useSession } from "../lib/session";

const STATION_KEY = "bmu.station";

function storedStation(): string {
  try {
    return window.localStorage.getItem(STATION_KEY) ?? "";
  } catch {
    return "";
  }
}

type Step = { kind: "password" } | { kind: "totp"; challenge: string; enroll?: { uri: string; secret: string } };

export function LoginPage() {
  const { t, lang } = useI18n();
  const { signIn } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [station, setStation] = useState(storedStation);
  const [code, setCode] = useState("");
  const [step, setStep] = useState<Step>({ kind: "password" });
  const [error, setError] = useState<string | null>(null);

  function finish(out: Schemas["LoginOut"]) {
    if (out.status === "OK" && out.access_token && out.me) {
      try {
        window.localStorage.setItem(STATION_KEY, station);
      } catch {
        /* ignore */
      }
      signIn(out.access_token, out.me);
      return;
    }
    if (out.challenge) {
      setCode("");
      setStep({
        kind: "totp",
        challenge: out.challenge,
        enroll:
          out.status === "TOTP_ENROLL" && out.otpauth_uri && out.totp_secret
            ? { uri: out.otpauth_uri, secret: out.totp_secret }
            : undefined,
      });
    }
  }

  const login = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/staff/auth/login", {
          body: { username: username.trim().toLowerCase(), password, station: station.trim() || null },
        }),
      ),
    onSuccess: (out) => {
      setError(null);
      finish(out);
    },
    onError: (e) => setError(errorMessage(t, e)),
  });

  const totp = useMutation({
    mutationFn: (challenge: string) => unwrap(api.POST("/api/v1/staff/auth/totp", { body: { challenge, code } })),
    onSuccess: (out) => {
      setError(null);
      finish(out);
    },
    onError: (e) => setError(errorMessage(t, e)),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (step.kind === "password") login.mutate();
    else totp.mutate(step.challenge);
  }

  return (
    <div className="grid min-h-dvh bg-paper paper-grain lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-brand-950 p-12 text-white lg:flex lg:flex-col">
        <Logo className="text-white" />
        <div className="mt-auto max-w-md">
          <p className="text-[13px] font-semibold uppercase tracking-[0.16em] text-brand-300">{t("common.institution")}</p>
          <h1 className="mt-3 text-[34px] font-bold leading-tight tracking-[-0.02em]">{t("staff.login.hero")}</h1>
          <p className="mt-4 text-[15px] leading-relaxed text-white/60">{t("staff.login.heroBody")}</p>
        </div>
        <div className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-brand-600/20 blur-3xl" />
      </aside>
      <main className="flex flex-col p-6 sm:p-10">
        <div className="flex items-center justify-between">
          <Logo className="lg:invisible" />
          <SegmentedControl
            size="sm"
            value={lang}
            onChange={setLanguage}
            options={[
              { value: "en", label: "EN" },
              { value: "bn", label: "বাং" },
            ]}
          />
        </div>
        <form onSubmit={submit} className="m-auto w-full max-w-sm py-10 animate-slide-up">
          {step.kind === "password" ? (
            <>
              <h2 className="text-2xl font-bold tracking-tight">{t("auth.staffTitle")}</h2>
              <p className="mt-1.5 text-[14px] text-sand-600">{t("auth.staffSubtitle")}</p>
              <div className="mt-7 space-y-4">
                <Field label={t("auth.username")} htmlFor="username">
                  <Input
                    id="username"
                    autoComplete="username"
                    autoFocus
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    inputSize="lg"
                  />
                </Field>
                <Field label={t("auth.password")} htmlFor="password">
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    inputSize="lg"
                  />
                </Field>
                <Field label={t("auth.station")} hint={t("auth.stationHint")} htmlFor="station">
                  <Input id="station" value={station} onChange={(e) => setStation(e.target.value)} />
                </Field>
              </div>
            </>
          ) : (
            <>
              <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-brand-50 text-brand-700">
                {step.enroll ? <ShieldCheck className="size-6" /> : <KeyRound className="size-6" />}
              </div>
              <h2 className="text-2xl font-bold tracking-tight">
                {step.enroll ? t("auth.totpEnrollTitle") : t("auth.totpTitle")}
              </h2>
              <p className="mt-1.5 text-[14px] text-sand-600">
                {step.enroll ? t("auth.totpEnrollSubtitle") : t("auth.totpSubtitle")}
              </p>
              {step.enroll && (
                <div className="mt-5 flex flex-col items-center rounded-2xl border border-sand-200 bg-white p-4">
                  <QrCode value={step.enroll.uri} size={176} label="otpauth" />
                  <p className="mt-3 text-[12px] text-sand-500">{t("auth.totpManual")}</p>
                  <code className="mt-1 break-all font-mono text-[13px] font-semibold tracking-wider" data-testid="totp-secret">
                    {step.enroll.secret}
                  </code>
                </div>
              )}
              <Field label={t("staff.login.code")} className="mt-5" htmlFor="totp">
                <Input
                  id="totp"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  maxLength={8}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  inputSize="xl"
                  className="text-center font-mono tracking-[0.4em]"
                />
              </Field>
            </>
          )}
          {error && (
            <Callout tone="danger" className="mt-4">
              {error}
            </Callout>
          )}
          <Button
            type="submit"
            block
            size="lg"
            className="mt-6"
            loading={login.isPending || totp.isPending}
            disabled={step.kind === "password" ? !username || !password : code.length < 6}
          >
            {step.kind === "password" ? t("auth.signIn") : t("auth.verify")}
          </Button>
          {step.kind === "totp" && (
            <button
              type="button"
              className="mt-3 w-full text-center text-[13px] font-semibold text-sand-500 hover:text-ink"
              onClick={() => setStep({ kind: "password" })}
            >
              {t("common.back")}
            </button>
          )}
          <p className="mt-8 text-center text-[12px] text-sand-400">{t("auth.secureNote")}</p>
        </form>
      </main>
    </div>
  );
}

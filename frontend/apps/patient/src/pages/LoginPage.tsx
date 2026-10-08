import { unwrap } from "@bmu/api-client";
import { digits, localMobile, useI18n } from "@bmu/i18n";
import { Button, Callout, Field, Input } from "@bmu/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquareText, Smartphone } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { changeLanguage, Screen } from "../components/Layout";
import { api, setTokens } from "../lib/api";
import { errorMessage } from "../lib/errors";
import { useSession } from "../lib/session";

/** Mobile number → 6-digit SMS code (ROADMAP §5.1 step 1). */
export function LoginPage() {
  const { t, lang } = useI18n();
  const { authed } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const [mobile, setMobile] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [wait, setWait] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  useEffect(() => {
    if (wait <= 0) return;
    const id = window.setTimeout(() => setWait((w) => w - 1), 1000);
    return () => window.clearTimeout(id);
  }, [wait]);

  const send = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/patient/auth/otp/request", { body: { mobile, lang } })),
    onSuccess: (out) => {
      setError(null);
      setSentTo(out.mobile);
      setDevCode(out.debug_code ?? null);
      setWait(out.resend_after);
      setCode("");
    },
    onError: (e) => setError(errorMessage(t, e)),
  });

  const verify = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/patient/auth/otp/verify", { body: { mobile: sentTo ?? mobile, code, lang } })),
    onSuccess: (out) => {
      setTokens(out);
      changeLanguage(lang);
      void qc.invalidateQueries({ queryKey: ["me"] });
      navigate(from, { replace: true });
    },
    onError: (e) => setError(errorMessage(t, e)),
  });

  if (authed) return <Navigate to={from} replace />;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (sentTo) verify.mutate();
    else send.mutate();
  }

  return (
    <Screen title={t("auth.otpTitle")}>
      <form onSubmit={submit} className="pt-6 animate-slide-up">
        <div className="mb-6 grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-700">
          {sentTo ? <MessageSquareText className="size-7" /> : <Smartphone className="size-7" />}
        </div>
        {!sentTo ? (
          <>
            <h2 className="text-[24px] font-bold leading-tight">{t("auth.otpTitle")}</h2>
            <p className="mt-2 text-[15px] text-sand-600">{t("auth.otpSubtitle")}</p>
            <Field label={t("auth.mobileLabel")} className="mt-6" htmlFor="mobile">
              <Input
                id="mobile"
                inputMode="tel"
                autoComplete="tel"
                placeholder="01XXXXXXXXX"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                inputSize="xl"
                autoFocus
                className="tracking-wider"
              />
            </Field>
          </>
        ) : (
          <>
            <h2 className="text-[24px] font-bold leading-tight">{t("auth.enterCode")}</h2>
            <p className="mt-2 text-[15px] text-sand-600">{t("auth.codeSentTo", { mobile: digits(localMobile(sentTo), lang) })}</p>
            <Field label={t("auth.enterCode")} className="mt-6" htmlFor="code">
              <Input
                id="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                inputSize="xl"
                autoFocus
                className="text-center font-mono tracking-[0.5em]"
              />
            </Field>
            {devCode && (
              <Callout tone="info" className="mt-3">
                {t("patient.login.devCode")} <b className="font-mono" data-testid="dev-code">{devCode}</b>
              </Callout>
            )}
            <div className="mt-3 flex items-center justify-between text-[14px]">
              <button type="button" className="font-semibold text-sand-600" onClick={() => setSentTo(null)}>
                {t("auth.changeNumber")}
              </button>
              {wait > 0 ? (
                <span className="text-sand-500">{t("auth.resendIn", { seconds: digits(wait, lang) })}</span>
              ) : (
                <button type="button" className="font-semibold text-brand-700" onClick={() => send.mutate()}>
                  {t("auth.resend")}
                </button>
              )}
            </div>
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
          size="xl"
          className="mt-8"
          loading={send.isPending || verify.isPending}
          disabled={sentTo ? code.length !== 6 : mobile.replace(/\D/g, "").length < 10}
        >
          {sentTo ? t("auth.verifyAndContinue") : t("auth.sendCode")}
        </Button>
        <p className="mt-6 text-center text-[13px] text-sand-500">{t("patient.login.privacy")}</p>
      </form>
    </Screen>
  );
}

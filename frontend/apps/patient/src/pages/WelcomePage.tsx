import { setLanguage, useI18n, type Lang } from "@bmu/i18n";
import { Button, Logo } from "@bmu/ui";
import { useNavigate } from "react-router-dom";

import { markWelcomed } from "../components/Layout";

/** First screen: choose the language (বাংলা by default). */
export function WelcomePage() {
  const { t } = useI18n();
  const navigate = useNavigate();

  function choose(lang: Lang) {
    setLanguage(lang);
    markWelcomed();
    navigate("/login", { replace: true });
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col bg-brand-950 px-6 pb-10 pt-16 text-white">
      <Logo className="[&_span]:text-white" />
      <div className="mt-auto">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-brand-300">{t("common.institution")}</p>
        <h1 className="mt-3 text-[30px] font-bold leading-tight">{t("patient.welcome.title")}</h1>
        <p className="mt-3 text-[16px] leading-relaxed text-white/70">{t("patient.welcome.body")}</p>
        <p className="mt-10 text-[13px] font-semibold text-white/50">{t("patient.welcome.chooseLanguage")}</p>
        <div className="mt-3 grid gap-3">
          <Button size="xl" variant="secondary" onClick={() => choose("bn")} lang="bn">
            বাংলা
          </Button>
          <Button size="xl" variant="outline" className="border-white/20 bg-transparent text-white hover:bg-white/10" onClick={() => choose("en")}>
            English
          </Button>
        </div>
      </div>
    </div>
  );
}

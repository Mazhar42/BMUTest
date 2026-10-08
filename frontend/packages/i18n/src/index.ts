import i18next, { type i18n as I18n } from "i18next";
import { initReactI18next, useTranslation } from "react-i18next";

import { resources } from "./resources";
import type { Lang } from "./format";

export * from "./format";

const STORAGE_KEY = "bmu.lang";

export function storedLanguage(fallback: Lang): Lang {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === "bn" || v === "en" ? v : fallback;
  } catch {
    return fallback;
  }
}

export function initI18n(defaultLang: Lang): I18n {
  const lng = storedLanguage(defaultLang);
  void i18next.use(initReactI18next).init({
    resources: { bn: { translation: resources.bn }, en: { translation: resources.en } },
    lng,
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    returnNull: false,
  });
  document.documentElement.lang = lng;
  return i18next;
}

export function setLanguage(lang: Lang): void {
  void i18next.changeLanguage(lang);
  document.documentElement.lang = lang;
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* private mode — language still applies for this session */
  }
}

/** `const { t, lang } = useI18n()` */
export function useI18n(): { t: ReturnType<typeof useTranslation>["t"]; lang: Lang; i18n: I18n } {
  const { t, i18n } = useTranslation();
  const lang: Lang = i18n.language === "bn" ? "bn" : "en";
  return { t, lang, i18n };
}

/** Translate an API error body `{code, message_key, params}` with a sensible fallback. */
export function translateError(
  t: ReturnType<typeof useTranslation>["t"],
  err: { code?: string; message_key?: string; params?: Record<string, unknown> } | null | undefined,
): string {
  if (!err) return t("errors.internal");
  const key = err.message_key ?? "errors.internal";
  const params = err.params ?? {};
  const translated = t(key, { ...params, defaultValue: "" });
  if (translated) return translated;
  const byCode = err.code ? t(`errors.${err.code.toLowerCase()}`, { ...params, defaultValue: "" }) : "";
  return byCode || t("errors.generic", { code: err.code ?? "?" });
}
export { flatKeys, resources } from "./resources";
export { missingKeys } from "./check-keys";

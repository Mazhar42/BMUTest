import { isApiError } from "@bmu/api-client";
import { translateError, useI18n } from "@bmu/i18n";
import { toast } from "@bmu/ui";
import { useCallback } from "react";

type T = ReturnType<typeof useI18n>["t"];

export function errorMessage(t: T, e: unknown): string {
  if (isApiError(e)) return translateError(t, e);
  if (e instanceof Error && e.message === "IMAGE_TOO_LARGE") return t("errors.image_too_large");
  return t("errors.internal");
}

export function useErrorToast(): (e: unknown) => void {
  const { t } = useI18n();
  return useCallback((e: unknown) => toast.error(errorMessage(t, e)), [t]);
}

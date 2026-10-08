import { isApiError } from "@bmu/api-client";
import { translateError, useI18n } from "@bmu/i18n";
import { toast } from "@bmu/ui";
import { useCallback } from "react";

type T = ReturnType<typeof useI18n>["t"];

export function errorMessage(t: T, e: unknown): string {
  if (isApiError(e)) return translateError(t, e);
  return t("errors.internal");
}

/** `const onError = useErrorToast()` → `useMutation({ onError })` */
export function useErrorToast(): (e: unknown) => void {
  const { t } = useI18n();
  return useCallback((e: unknown) => toast.error(errorMessage(t, e)), [t]);
}

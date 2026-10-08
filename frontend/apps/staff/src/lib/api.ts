import { createApi, fetchBlobUrl, postForm, type Schemas } from "@bmu/api-client";
import { QueryClient } from "@tanstack/react-query";

const TOKEN_KEY = "bmu.staff.token";

type Listener = () => void;
const lockListeners = new Set<Listener>();
const logoutListeners = new Set<Listener>();

export const tokenStore = {
  get(): string | null {
    try {
      return window.sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null): void {
    try {
      if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
      else window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export function onLocked(fn: Listener): () => void {
  lockListeners.add(fn);
  return () => lockListeners.delete(fn);
}

export function onLoggedOut(fn: Listener): () => void {
  logoutListeners.add(fn);
  return () => logoutListeners.delete(fn);
}

export const api = createApi({
  getToken: () => tokenStore.get(),
  onLocked: () => lockListeners.forEach((fn) => fn()),
  onUnauthorized: (code) => {
    if (code === "INVALID_CREDENTIALS" || code === "INVALID_TOTP" || code === "CHALLENGE_EXPIRED") return;
    tokenStore.set(null);
    logoutListeners.forEach((fn) => fn());
  },
});

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, err) => {
        const status = (err as { status?: number }).status ?? 0;
        return status === 0 && count < 2;
      },
      refetchOnWindowFocus: true,
      staleTime: 10_000,
    },
  },
});

export type Me = Schemas["StaffMe"];

/** Upload multipart form data (prescription photos, CSV imports) as the signed-in staff user. */
export function upload<T>(path: string, form: FormData): Promise<T> {
  return postForm<T>(path, form, tokenStore.get());
}

/** A protected image (prescription page) as an object URL; the caller revokes it. */
export function protectedImage(path: string): Promise<string> {
  return fetchBlobUrl(path, tokenStore.get());
}

/** Download a protected PDF and open the browser print dialog (silent with --kiosk-printing). */
export async function printPdf(path: string, method: "GET" | "POST" = "GET"): Promise<void> {
  const url = await fetchBlobUrl(path, tokenStore.get(), { method });
  const frame = document.createElement("iframe");
  frame.style.position = "fixed";
  frame.style.right = "0";
  frame.style.bottom = "0";
  frame.style.width = "0";
  frame.style.height = "0";
  frame.style.border = "0";
  frame.src = url;
  document.body.appendChild(frame);
  await new Promise<void>((resolve) => {
    frame.onload = () => {
      window.setTimeout(() => {
        frame.contentWindow?.focus();
        frame.contentWindow?.print();
        resolve();
      }, 250);
    };
  });
  window.setTimeout(() => {
    frame.remove();
    URL.revokeObjectURL(url);
  }, 60_000);
}

/** Open a protected PDF in a new tab. */
export async function openPdf(path: string, method: "GET" | "POST" = "GET"): Promise<void> {
  const win = window.open("", "_blank");
  const url = await fetchBlobUrl(path, tokenStore.get(), { method });
  if (win) win.location.href = url;
  else window.location.href = url;
}

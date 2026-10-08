import { createApi, postForm, type Schemas } from "@bmu/api-client";
import { QueryClient } from "@tanstack/react-query";

/** The access token lives only in memory (15 min). The refresh token is an httpOnly cookie that the
 *  server rotates on every refresh, so a reload simply calls /refresh to get a new access token. */
let accessToken: string | null = null;
let expiresAt = 0;
let refreshing: Promise<string | null> | null = null;
const listeners = new Set<() => void>();

export function onSessionChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify() {
  listeners.forEach((fn) => fn());
}

export function setTokens(out: Schemas["PatientTokenOut"] | null): void {
  accessToken = out?.access_token ?? null;
  expiresAt = out ? Date.now() + out.expires_in * 1000 : 0;
  notify();
}

export function hasSession(): boolean {
  return accessToken !== null;
}

export function refresh(): Promise<string | null> {
  refreshing ??= fetch("/api/v1/patient/auth/refresh", {
    method: "POST",
    credentials: "include",
    headers: { "X-Requested-With": "bmu" },
  })
    .then(async (r) => {
      if (!r.ok) {
        setTokens(null);
        return null;
      }
      const out = (await r.json()) as Schemas["PatientTokenOut"];
      setTokens(out);
      return out.access_token;
    })
    .catch(() => accessToken)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function token(): Promise<string | null> {
  if (accessToken && Date.now() < expiresAt - 30_000) return accessToken;
  if (!accessToken) return null;
  return refresh();
}

export const api = createApi({
  getToken: token,
  onUnauthorized: (code) => {
    if (code.startsWith("OTP_")) return;
    setTokens(null);
  },
});

export async function upload<T>(path: string, form: FormData): Promise<T> {
  return postForm<T>(path, form, await token());
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/v1/patient/auth/logout", {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "bmu" },
    });
  } finally {
    setTokens(null);
    queryClient.clear();
  }
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, err) => ((err as { status?: number }).status ?? 0) === 0 && count < 2,
      staleTime: 15_000,
    },
  },
});

/** The last orders, kept so the confirmation QR is still visible offline (ROADMAP §11). */
const OFFLINE_KEY = "bmu.lastOrders";

export function saveOffline(orders: Schemas["OrderOut"][]): void {
  try {
    window.localStorage.setItem(OFFLINE_KEY, JSON.stringify(orders.slice(0, 10)));
  } catch {
    /* storage full or blocked */
  }
}

export function loadOffline(): Schemas["OrderOut"][] {
  try {
    return JSON.parse(window.localStorage.getItem(OFFLINE_KEY) ?? "[]") as Schemas["OrderOut"][];
  } catch {
    return [];
  }
}

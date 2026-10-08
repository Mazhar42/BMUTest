import { unwrap } from "@bmu/api-client";
import { setLanguage } from "@bmu/i18n";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, onLocked, onLoggedOut, tokenStore, type Me } from "./api";

interface SessionValue {
  me: Me | null;
  loading: boolean;
  locked: boolean;
  setLocked: (v: boolean) => void;
  signIn: (token: string, me: Me) => void;
  signOut: () => Promise<void>;
  can: (...perms: string[]) => boolean;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [hasToken, setHasToken] = useState(() => !!tokenStore.get());
  const [locked, setLocked] = useState(false);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => unwrap(api.GET("/api/v1/staff/auth/me")),
    enabled: hasToken,
    staleTime: 60_000,
  });

  useEffect(() => onLocked(() => setLocked(true)), []);
  useEffect(
    () =>
      onLoggedOut(() => {
        setHasToken(false);
        setLocked(false);
        qc.clear();
      }),
    [qc],
  );

  useEffect(() => {
    const lang = meQuery.data?.preferred_language;
    if (lang === "bn" || lang === "en") setLanguage(lang);
  }, [meQuery.data?.preferred_language]);

  const signIn = useCallback(
    (token: string, me: Me) => {
      tokenStore.set(token);
      qc.setQueryData(["me"], me);
      setHasToken(true);
      setLocked(false);
    },
    [qc],
  );

  const signOut = useCallback(async () => {
    try {
      await api.POST("/api/v1/staff/auth/logout");
    } finally {
      tokenStore.set(null);
      setHasToken(false);
      setLocked(false);
      qc.clear();
    }
  }, [qc]);

  const me = hasToken ? (meQuery.data ?? null) : null;
  const value = useMemo<SessionValue>(
    () => ({
      me,
      loading: hasToken && meQuery.isLoading,
      locked,
      setLocked,
      signIn,
      signOut,
      can: (...perms) => !!me && perms.some((p) => me.permissions.includes(p)),
    }),
    [me, hasToken, meQuery.isLoading, locked, signIn, signOut],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside SessionProvider");
  return ctx;
}

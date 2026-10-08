import { unwrap, type Schemas } from "@bmu/api-client";
import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, hasSession, onSessionChange, refresh } from "./api";

interface SessionValue {
  ready: boolean;
  authed: boolean;
  account: Schemas["AccountOut"] | null;
  reloadAccount: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(hasSession());

  useEffect(() => onSessionChange(() => setAuthed(hasSession())), []);
  useEffect(() => {
    void refresh().finally(() => setReady(true));
  }, []);

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => unwrap(api.GET("/api/v1/patient/me")),
    enabled: authed,
  });

  const value = useMemo<SessionValue>(
    () => ({
      ready,
      authed,
      account: authed ? (me.data ?? null) : null,
      reloadAccount: () => void me.refetch(),
    }),
    [ready, authed, me],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside SessionProvider");
  return ctx;
}

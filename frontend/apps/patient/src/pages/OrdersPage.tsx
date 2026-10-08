import { unwrap } from "@bmu/api-client";
import { formatDate, formatMoney, useI18n } from "@bmu/i18n";
import { Button, EmptyState, OrderCode, Skeleton } from "@bmu/ui";
import { useQuery } from "@tanstack/react-query";
import { CalendarX2, ChevronRight } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { Screen } from "../components/Layout";
import { api, loadOffline, saveOffline } from "../lib/api";
import { StatusPill } from "./OrderPage";

/** My Appointments: every request with its status. Slots arrive with M5. */
export default function OrdersPage() {
  const { t, lang } = useI18n();
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => unwrap(api.GET("/api/v1/patient/orders")) });
  useEffect(() => {
    if (orders.data) saveOffline(orders.data);
  }, [orders.data]);
  const rows = orders.data ?? (orders.isError ? loadOffline() : []);

  return (
    <Screen back="/" title={t("patient.home.appointments")}>
      {orders.isLoading ? (
        <Skeleton className="mt-4 h-40" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<CalendarX2 className="size-6" />}
          title={t("patient.orders.empty")}
          body={t("patient.orders.emptyBody")}
          action={
            <Link to="/book">
              <Button size="lg">{t("patient.home.book")}</Button>
            </Link>
          }
        />
      ) : (
        <ul className="mt-3 grid gap-3">
          {rows.map((o) => (
            <li key={o.id}>
              <Link
                to={`/orders/${o.id}`}
                data-testid="order-row"
                className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-card ring-1 ring-sand-200"
              >
                <span className="min-w-0 flex-1">
                  <OrderCode code={o.order_code ?? ""} size="sm" />
                  <span className="mt-1 block truncate text-[15px] font-semibold">
                    {o.patient.full_name} · {o.items.map((i) => i.abbreviation).join(", ")}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-2 text-[13px] text-sand-500">
                    <StatusPill status={o.status} />
                    {formatDate(o.submitted_at, lang, "short")} · {formatMoney(o.total, lang)}
                  </span>
                </span>
                <ChevronRight className="size-5 text-sand-400" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Screen>
  );
}

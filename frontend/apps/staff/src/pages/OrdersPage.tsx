import { unwrap } from "@bmu/api-client";
import { formatDateTime, formatMoney, useI18n } from "@bmu/i18n";
import { Button, Card, EmptyState, Input, OrderCode, PageHeader, Select, Table, TD, TH, TR } from "@bmu/ui";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ListOrdered, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { useNavigate } from "react-router-dom";

import { OrderStatusBadge, PriorityBadge } from "../components/StatusBadge";
import { api } from "../lib/api";

const STATUSES = [
  "PENDING_VERIFICATION",
  "NEEDS_CLARIFICATION",
  "AWAITING_PAYMENT",
  "PAID",
  "REJECTED",
  "CANCELLED",
  "EXPIRED",
] as const;
type Status = (typeof STATUSES)[number];

export default function OrdersPage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [status, setStatus] = useState<Status | "">("");
  const [q, setQ] = useState("");
  const query = useDeferredValue(q.trim());

  const orders = useInfiniteQuery({
    queryKey: ["orders", status, query],
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/staff/orders", {
          params: { query: { status: status || null, q: query || null, cursor: pageParam, limit: 50 } },
        }),
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = orders.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div>
      <PageHeader eyebrow={t("nav.groups.frontDesk")} title={t("nav.items.orders")} subtitle={t("staff.orders.subtitle")} />
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-sand-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("staff.orders.searchPlaceholder")} className="pl-10" />
        </div>
        <Select value={status} onChange={(e) => setStatus(e.target.value as Status | "")} className="w-60">
          <option value="">{t("common.all")}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`enums.orderStatus.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      <Card>
        {rows.length === 0 && !orders.isLoading ? (
          <EmptyState icon={<ListOrdered className="size-6" />} title={t("common.noResults")} />
        ) : (
          <Table>
            <thead>
              <tr>
                <TH>{t("common.code")}</TH>
                <TH>{t("staff.orders.patient")}</TH>
                <TH>{t("staff.orders.tests")}</TH>
                <TH>{t("common.total")}</TH>
                <TH>{t("staff.orders.channel")}</TH>
                <TH>{t("staff.verify.submitted")}</TH>
                <TH>{t("common.status")}</TH>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <TR key={row.id} className="cursor-pointer" onClick={() => navigate(`/orders/${row.order_code ?? row.id}`)}>
                  <TD>
                    <OrderCode code={row.order_code ?? ""} size="sm" />
                  </TD>
                  <TD>
                    <span className="font-semibold">{row.patient_name}</span> <PriorityBadge priority={row.priority} />
                  </TD>
                  <TD className="max-w-xs truncate text-[13px]">{row.tests.join(", ")}</TD>
                  <TD className="tabular">{formatMoney(row.total, lang)}</TD>
                  <TD className="text-[13px]">{t(`enums.channel.${row.channel}`)}</TD>
                  <TD className="text-[13px] text-sand-600">{formatDateTime(row.submitted_at, lang)}</TD>
                  <TD>
                    <OrderStatusBadge status={row.status} />
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      {orders.hasNextPage && (
        <div className="mt-4 text-center">
          <Button variant="outline" loading={orders.isFetchingNextPage} onClick={() => void orders.fetchNextPage()}>
            {t("common.showMore")}
          </Button>
        </div>
      )}
    </div>
  );
}

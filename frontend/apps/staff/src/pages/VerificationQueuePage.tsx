import { unwrap, type Schemas } from "@bmu/api-client";
import { formatMoney, formatRelative, useI18n } from "@bmu/i18n";
import {
  Badge,
  Card,
  EmptyState,
  formatDuration,
  OrderCode,
  PageHeader,
  SegmentedControl,
  Table,
  TD,
  TH,
  TR,
  useCountdown,
} from "@bmu/ui";
import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { PriorityBadge } from "../components/StatusBadge";
import { api } from "../lib/api";

type Status = "PENDING_VERIFICATION" | "NEEDS_CLARIFICATION";

export function SlaCell({ row }: { row: Schemas["OrderRow"] }) {
  const { t } = useI18n();
  const left = useCountdown(row.sla_due_at);
  if (!row.sla_due_at) return <span className="text-sand-400">—</span>;
  if (row.overdue || left <= 0) return <Badge tone="danger" dot>{t("staff.verify.overdue")}</Badge>;
  return (
    <span className={left < 30 * 60_000 ? "font-semibold text-warn-700 tabular" : "tabular text-sand-600"}>
      {formatDuration(left)}
    </span>
  );
}

export default function VerificationQueuePage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [status, setStatus] = useState<Status>("PENDING_VERIFICATION");
  const queue = useQuery({
    queryKey: ["verification-queue", status],
    queryFn: () => unwrap(api.GET("/api/v1/staff/verification/queue", { params: { query: { status } } })),
    refetchInterval: 15_000,
  });
  const rows = queue.data ?? [];

  return (
    <div>
      <PageHeader
        eyebrow={t("nav.groups.frontDesk")}
        title={t("nav.items.verification")}
        subtitle={t("staff.verify.queueSubtitle")}
        actions={
          <SegmentedControl
            value={status}
            onChange={setStatus}
            options={[
              { value: "PENDING_VERIFICATION", label: t("enums.orderStatus.PENDING_VERIFICATION") },
              { value: "NEEDS_CLARIFICATION", label: t("enums.orderStatus.NEEDS_CLARIFICATION") },
            ]}
          />
        }
      />
      <Card>
        {rows.length === 0 && !queue.isLoading ? (
          <EmptyState icon={<ClipboardCheck className="size-6" />} title={t("staff.verify.empty")} body={t("staff.verify.emptyBody")} />
        ) : (
          <Table>
            <thead>
              <tr>
                <TH>{t("common.code")}</TH>
                <TH>{t("staff.orders.patient")}</TH>
                <TH>{t("staff.orders.tests")}</TH>
                <TH>{t("common.total")}</TH>
                <TH>{t("staff.verify.submitted")}</TH>
                <TH>{t("staff.verify.sla")}</TH>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <TR
                  key={row.id}
                  className={row.overdue ? "cursor-pointer bg-danger-50/40" : "cursor-pointer"}
                  onClick={() => navigate(`/verification/${row.id}`)}
                  data-testid="queue-row"
                >
                  <TD>
                    <OrderCode code={row.order_code ?? ""} size="sm" />
                  </TD>
                  <TD>
                    <div className="font-semibold">{row.patient_name}</div>
                    <div className="text-[12px] text-sand-500">
                      {row.patient_age ?? "—"} · {t(`common.sexes.${row.patient_sex}`)} <PriorityBadge priority={row.priority} />
                    </div>
                  </TD>
                  <TD className="max-w-xs truncate text-[13px]">{row.tests.join(", ")}</TD>
                  <TD className="tabular">{formatMoney(row.total, lang)}</TD>
                  <TD className="text-[13px] text-sand-600">{formatRelative(row.submitted_at, lang)}</TD>
                  <TD>
                    <SlaCell row={row} />
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

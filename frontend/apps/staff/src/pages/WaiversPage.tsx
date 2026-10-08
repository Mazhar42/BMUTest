import { unwrap, type Schemas } from "@bmu/api-client";
import { formatMoney, formatRelative, useI18n } from "@bmu/i18n";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  Field,
  Input,
  OrderCode,
  PageHeader,
  SegmentedControl,
  Table,
  TD,
  TH,
  Textarea,
  toast,
  TR,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stamp } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { PriorityBadge, WaiverStatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { useErrorToast } from "../lib/errors";
import { useSession } from "../lib/session";

type Status = "REQUESTED" | "APPROVED" | "DECLINED";
type Row = Schemas["WaiverQueueRow"];

/** Emergency / free / poor fund / staff concession decisions (ROADMAP §5.4). */
export default function WaiversPage() {
  const { t, lang } = useI18n();
  const { can, me } = useSession();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [status, setStatus] = useState<Status>("REQUESTED");
  const [deciding, setDeciding] = useState<{ row: Row; approve: boolean } | null>(null);
  const [discountTaka, setDiscountTaka] = useState("");
  const [reason, setReason] = useState("");

  const list = useQuery({
    queryKey: ["waivers", status],
    queryFn: () => unwrap(api.GET("/api/v1/staff/waivers", { params: { query: { status } } })),
  });

  const decide = useMutation({
    mutationFn: () => {
      if (!deciding) throw new Error("none");
      return unwrap(
        api.POST("/api/v1/staff/waivers/{waiver_id}/decision", {
          params: { path: { waiver_id: deciding.row.waiver.id } },
          body: {
            approve: deciding.approve,
            discount: deciding.approve ? Math.round(Number(discountTaka) * 100) : null,
            reason: reason.trim(),
          },
        }),
      );
    },
    onSuccess: () => {
      toast.success(t(deciding?.approve ? "staff.waivers.approved" : "staff.waivers.declined"));
      setDeciding(null);
      void qc.invalidateQueries({ queryKey: ["waivers"] });
    },
    onError,
  });

  function open(row: Row, approve: boolean) {
    setDiscountTaka(String(row.order.total / 100));
    setReason("");
    setDeciding({ row, approve });
  }

  const rows = list.data ?? [];
  const discountPaisa = Math.round(Number(discountTaka) * 100);
  const validDiscount = !deciding?.approve || (discountPaisa > 0 && discountPaisa <= (deciding?.row.order.total ?? 0));

  return (
    <div>
      <PageHeader
        eyebrow={t("nav.groups.frontDesk")}
        title={t("nav.items.waivers")}
        subtitle={t("staff.waivers.subtitle")}
        actions={
          <SegmentedControl
            value={status}
            onChange={setStatus}
            options={(["REQUESTED", "APPROVED", "DECLINED"] as const).map((s) => ({ value: s, label: t(`enums.waiverStatus.${s}`) }))}
          />
        }
      />
      <Card>
        {rows.length === 0 && !list.isLoading ? (
          <EmptyState icon={<Stamp className="size-6" />} title={t("staff.waivers.empty")} />
        ) : (
          <Table>
            <thead>
              <tr>
                <TH>{t("common.code")}</TH>
                <TH>{t("staff.orders.patient")}</TH>
                <TH>{t("staff.helpdesk.feeCategory")}</TH>
                <TH>{t("common.reason")}</TH>
                <TH>{t("common.amount")}</TH>
                <TH>{t("common.status")}</TH>
                <TH />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <TR key={row.waiver.id}>
                  <TD>
                    <Link to={`/orders/${row.order.order_code}`} className="hover:underline">
                      <OrderCode code={row.order.order_code ?? ""} size="sm" />
                    </Link>
                    <div className="mt-0.5 text-[12px] text-sand-500">{formatRelative(row.waiver.created_at, lang)}</div>
                  </TD>
                  <TD>
                    <div className="font-semibold">{row.order.patient_name}</div>
                    <div className="text-[12px] text-sand-500">
                      {row.order.tests.join(", ")} <PriorityBadge priority={row.order.priority} />
                    </div>
                  </TD>
                  <TD>
                    <Badge tone="warn">{t(`enums.feeCategory.${row.waiver.fee_category}`)}</Badge>
                  </TD>
                  <TD className="max-w-xs text-[13px]">{row.waiver.request_reason}</TD>
                  <TD className="tabular">
                    {formatMoney(row.subtotal, lang)}
                    {row.waiver.approved_discount !== null && (
                      <div className="text-[12px] text-ok-600">−{formatMoney(row.waiver.approved_discount, lang)}</div>
                    )}
                  </TD>
                  <TD>
                    <WaiverStatusBadge status={row.waiver.status} />
                  </TD>
                  <TD className="text-right">
                    {row.waiver.status === "REQUESTED" && can("waiver.approve") && row.waiver.requested_by !== me?.id && (
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" onClick={() => open(row, true)} data-testid="waiver-approve">
                          {t("staff.waivers.approve")}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => open(row, false)}>
                          {t("staff.waivers.decline")}
                        </Button>
                      </div>
                    )}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <Dialog
        open={!!deciding}
        onOpenChange={(v) => !v && setDeciding(null)}
        title={deciding?.approve ? t("staff.waivers.approveTitle") : t("staff.waivers.declineTitle")}
        description={deciding ? `${deciding.row.order.patient_name} · ${t(`enums.feeCategory.${deciding.row.waiver.fee_category}`)}` : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeciding(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant={deciding?.approve ? "primary" : "danger"}
              loading={decide.isPending}
              disabled={reason.trim().length < 3 || !validDiscount}
              onClick={() => decide.mutate()}
            >
              {deciding?.approve ? t("staff.waivers.approve") : t("staff.waivers.decline")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {deciding?.approve && (
            <Field
              label={t("staff.waivers.discount")}
              hint={t("staff.waivers.discountHint", { total: formatMoney(deciding.row.order.total, lang) })}
            >
              <Input type="number" min={1} step="0.01" value={discountTaka} onChange={(e) => setDiscountTaka(e.target.value)} />
            </Field>
          )}
          <Field label={t("common.reason")} hint={t("staff.waivers.reasonHint")}>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
        </div>
      </Dialog>
    </div>
  );
}

import { isApiError, unwrap } from "@bmu/api-client";
import { formatDateTime, formatMoney, useI18n } from "@bmu/i18n";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Dialog,
  EmptyState,
  Field,
  OrderCode,
  PageHeader,
  Select,
  Skeleton,
  Table,
  TD,
  Textarea,
  TH,
  Timeline,
  toast,
  TR,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, ClipboardCheck, Printer, Stamp } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ImageViewer } from "../components/ImageViewer";
import { patientLine } from "../components/PatientFinder";
import { OrderStatusBadge, PriorityBadge, WaiverStatusBadge } from "../components/StatusBadge";
import { api, printPdf } from "../lib/api";
import { errorMessage, useErrorToast } from "../lib/errors";
import { useSession } from "../lib/session";

const OPEN = ["DRAFT", "PENDING_VERIFICATION", "NEEDS_CLARIFICATION", "AWAITING_PAYMENT"];
const WAIVABLE = ["FREE", "POOR_FUND", "STAFF", "CONCESSION"] as const;

export default function OrderDetailPage() {
  const { ref = "" } = useParams();
  const { t, lang } = useI18n();
  const { can } = useSession();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [dialog, setDialog] = useState<"cancel" | "waiver" | null>(null);
  const [reason, setReason] = useState("");
  const [fee, setFee] = useState<(typeof WAIVABLE)[number]>("POOR_FUND");

  const order = useQuery({
    queryKey: ["order", ref],
    queryFn: () => unwrap(api.GET("/api/v1/staff/orders/{ref}", { params: { path: { ref } } })),
    retry: false,
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["order", ref] });

  const print = useMutation({
    mutationFn: (id: string) => printPdf(`/api/v1/staff/orders/${id}/slip`, "POST"),
    onSuccess: refresh,
    onError,
  });
  const cancel = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.POST("/api/v1/staff/orders/{order_id}/cancel", { params: { path: { order_id: id } }, body: { reason } })),
    onSuccess: () => {
      setDialog(null);
      toast.success(t("staff.orderDetail.cancelled"));
      refresh();
    },
    onError,
  });
  const waiver = useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.POST("/api/v1/staff/orders/{order_id}/waivers", {
          params: { path: { order_id: id } },
          body: { fee_category: fee, reason },
        }),
      ),
    onSuccess: () => {
      setDialog(null);
      toast.success(t("staff.orderDetail.waiverRequested"));
      refresh();
    },
    onError,
  });

  if (order.isLoading) return <Skeleton className="h-96" />;
  if (order.error || !order.data) {
    return (
      <Card>
        <EmptyState
          title={isApiError(order.error) && order.error.code === "CODE_MISTYPED" ? t("errors.code_mistyped") : t("errors.not_found")}
          body={order.error ? errorMessage(t, order.error) : undefined}
        />
      </Card>
    );
  }
  const o = order.data;
  const openWaiver = o.waivers.some((w) => w.status === "REQUESTED");

  return (
    <div>
      <PageHeader
        eyebrow={t("nav.items.orders")}
        title={<OrderCode code={o.order_code ?? ""} size="xl" />}
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-2">
            <OrderStatusBadge status={o.status} />
            <PriorityBadge priority={o.priority} />
            <span>{t(`enums.channel.${o.channel}`)}</span>
            {o.overdue && <Badge tone="danger">{t("staff.verify.overdue")}</Badge>}
          </span>
        }
        actions={
          <>
            {o.status === "PENDING_VERIFICATION" && can("order.verify") && (
              <Link to={`/verification/${o.id}`}>
                <Button icon={<ClipboardCheck className="size-4" />}>{t("staff.orderDetail.verify")}</Button>
              </Link>
            )}
            {can("order.reprint_slip", "order.create_walkin") && !["REJECTED", "CANCELLED", "EXPIRED", "PENDING_VERIFICATION", "NEEDS_CLARIFICATION"].includes(o.status) && (
              <Button variant="outline" icon={<Printer className="size-4" />} loading={print.isPending} onClick={() => print.mutate(o.id)}>
                {o.slip_print_count ? t("common.reprint") : t("staff.orderDetail.printSlip")}
              </Button>
            )}
            {o.status === "AWAITING_PAYMENT" && can("waiver.request") && !openWaiver && (
              <Button variant="outline" icon={<Stamp className="size-4" />} onClick={() => { setReason(""); setDialog("waiver"); }}>
                {t("staff.orderDetail.requestWaiver")}
              </Button>
            )}
            {OPEN.includes(o.status) && can("order.cancel") && (
              <Button variant="ghost" className="text-danger-600" icon={<Ban className="size-4" />} onClick={() => { setReason(""); setDialog("cancel"); }}>
                {t("common.cancel")}
              </Button>
            )}
          </>
        }
      />
      {o.status_reason && (
        <Callout tone={o.status === "REJECTED" ? "danger" : "info"} className="mb-5" title={t("common.reason")}>
          {o.status_reason}
        </Callout>
      )}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card>
            <CardHeader title={o.patient.full_name} subtitle={patientLine(o.patient, t)} />
            <Table>
              <thead>
                <tr>
                  <TH>{t("staff.orders.tests")}</TH>
                  <TH>{t("staff.orderDetail.container")}</TH>
                  <TH>{t("staff.orderDetail.prep")}</TH>
                  <TH className="text-right">{t("common.amount")}</TH>
                </tr>
              </thead>
              <tbody>
                {o.items.map((i) => (
                  <TR key={i.id}>
                    <TD>
                      <div className="font-semibold">{lang === "bn" ? i.test_name_bn : i.test_name_en}</div>
                      <div className="text-[12px] text-sand-500">{i.test_code}</div>
                    </TD>
                    <TD className="text-[13px]">{i.container_type ? t(`enums.container.${i.container_type}`) : "—"}</TD>
                    <TD className="text-[13px]">
                      {i.fasting_required ? t("staff.orderDetail.fasting", { hours: i.fasting_hours ?? "?" }) : "—"}
                    </TD>
                    <TD className="text-right tabular">{formatMoney(i.price_snapshot, lang)}</TD>
                  </TR>
                ))}
              </tbody>
              <tfoot>
                {o.discount > 0 && (
                  <tr>
                    <TD colSpan={3} className="text-right text-sand-500">{t("staff.orderDetail.discount")}</TD>
                    <TD className="text-right tabular text-ok-600">−{formatMoney(o.discount, lang)}</TD>
                  </tr>
                )}
                <tr>
                  <TD colSpan={3} className="text-right font-semibold">{t("common.total")}</TD>
                  <TD className="text-right text-lg font-bold tabular">{formatMoney(o.total, lang)}</TD>
                </tr>
              </tfoot>
            </Table>
          </Card>
          {o.prescription && (
            <div className="h-[520px]">
              <ImageViewer prescriptionId={o.prescription.id} pages={o.prescription.image_count} />
            </div>
          )}
        </div>
        <div className="space-y-5">
          <Card>
            <CardHeader title={t("staff.orderDetail.progress")} />
            <CardBody>
              <Timeline
                steps={o.timeline.map((s) => ({
                  key: s.key,
                  state: s.state,
                  title: t(`enums.timeline.${s.key}`),
                  detail: s.note ?? undefined,
                  at: s.at ? formatDateTime(s.at, lang) : undefined,
                }))}
              />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title={t("staff.orderDetail.money")} />
            <CardBody className="space-y-2 text-[14px]">
              <div className="flex justify-between">
                <span className="text-sand-500">{t("staff.helpdesk.feeCategory")}</span>
                <span>{t(`enums.feeCategory.${o.fee_category}`)}</span>
              </div>
              {o.waivers.map((w) => (
                <div key={w.id} className="rounded-xl bg-sand-50 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{t(`enums.feeCategory.${w.fee_category}`)}</span>
                    <WaiverStatusBadge status={w.status} />
                  </div>
                  <p className="mt-1 text-[13px] text-sand-600">{w.request_reason}</p>
                  {w.status_reason && <p className="mt-1 text-[13px] text-sand-500">→ {w.status_reason}</p>}
                </div>
              ))}
              {o.payments.map((p) => (
                <div key={p.id} className="flex justify-between">
                  <span>{t(`enums.paymentMethod.${p.method}`)}</span>
                  <span className="tabular">{formatMoney(p.amount, lang)}</span>
                </div>
              ))}
              <div className="flex justify-between border-t border-sand-100 pt-2 font-semibold">
                <span>{t("staff.orderDetail.due")}</span>
                <span className="tabular">{formatMoney(o.amount_due, lang)}</span>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>
      <Dialog
        open={dialog !== null}
        onOpenChange={(v) => !v && setDialog(null)}
        title={dialog === "cancel" ? t("staff.orderDetail.cancelTitle") : t("staff.orderDetail.requestWaiver")}
        tone={dialog === "cancel" ? "danger" : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(null)}>
              {t("common.close")}
            </Button>
            <Button
              variant={dialog === "cancel" ? "danger" : "primary"}
              disabled={reason.trim().length < 3}
              loading={cancel.isPending || waiver.isPending}
              onClick={() => (dialog === "cancel" ? cancel.mutate(o.id) : waiver.mutate(o.id))}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {dialog === "waiver" && (
            <Field label={t("staff.helpdesk.feeCategory")}>
              <Select value={fee} onChange={(e) => setFee(e.target.value as typeof fee)}>
                {WAIVABLE.map((c) => (
                  <option key={c} value={c}>
                    {t(`enums.feeCategory.${c}`)}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Field label={t("common.reason")}>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
          </Field>
        </div>
      </Dialog>
    </div>
  );
}

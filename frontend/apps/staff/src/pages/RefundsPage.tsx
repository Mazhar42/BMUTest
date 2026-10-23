import { unwrap, type Schemas } from "@bmu/api-client";
import { formatDateTime, formatMoney, formatRelative, useI18n } from "@bmu/i18n";
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
  Input,
  OrderCode,
  PageHeader,
  SegmentedControl,
  Select,
  Table,
  TD,
  Textarea,
  TH,
  toast,
  TR,
  type Tone,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HandCoins, Search } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { useErrorToast } from "../lib/errors";
import { useSession } from "../lib/session";

type Status = "REQUESTED" | "COMPLETED" | "REJECTED" | "FAILED";
type Row = Schemas["RefundRow"];
const PAY_TONE: Record<string, Tone> = { SUCCESS: "ok", REFUND_PENDING: "warn", REFUNDED: "neutral", FAILED: "danger" };

export default function RefundsPage() {
  const { t, lang } = useI18n();
  const { can, me } = useSession();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [status, setStatus] = useState<Status>("REQUESTED");
  const [code, setCode] = useState("");
  const [searched, setSearched] = useState("");
  const [requesting, setRequesting] = useState<Schemas["PaymentOut"] | null>(null);
  const [reason, setReason] = useState("");
  const [deciding, setDeciding] = useState<{ row: Row; approve: boolean } | null>(null);
  const [mode, setMode] = useState<"MANUAL" | "PROVIDER">("MANUAL");
  const [reference, setReference] = useState("");

  const queue = useQuery({
    queryKey: ["refunds", status],
    queryFn: () => unwrap(api.GET("/api/v1/staff/refunds", { params: { query: { status } } })),
  });
  const order = useQuery({
    queryKey: ["order-payments", searched],
    queryFn: () => unwrap(api.GET("/api/v1/staff/payments/by-order/{ref}", { params: { path: { ref: searched } } })),
    enabled: !!searched,
    retry: false,
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["refunds"] });
    void qc.invalidateQueries({ queryKey: ["order-payments"] });
  };
  const request = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/staff/payments/{payment_id}/refund", {
          params: { path: { payment_id: requesting!.id } },
          body: { reason: reason.trim() },
        }),
      ),
    onSuccess: () => {
      toast.success(t("staff.refunds.requested"));
      setRequesting(null);
      setReason("");
      refresh();
    },
    onError,
  });
  const decide = useMutation({
    mutationFn: () => {
      const id = deciding!.row.id;
      return deciding!.approve
        ? unwrap(
            api.POST("/api/v1/staff/refunds/{refund_id}/approve", {
              params: { path: { refund_id: id } },
              body: { mode, manual_reference: mode === "MANUAL" ? reference.trim() : null },
            }),
          )
        : unwrap(api.POST("/api/v1/staff/refunds/{refund_id}/reject", { params: { path: { refund_id: id } }, body: { reason: reason.trim() } }));
    },
    onSuccess: (r) => {
      toast[r.status === "FAILED" ? "error" : "success"](t(r.status === "FAILED" ? "staff.refunds.providerFailed" : "staff.refunds.done"));
      setDeciding(null);
      setReason("");
      setReference("");
      refresh();
    },
    onError,
  });

  function search(e: FormEvent) {
    e.preventDefault();
    setSearched(code.trim());
  }
  function openDecision(row: Row, approve: boolean) {
    setMode(row.payment_method === "GATEWAY" ? "PROVIDER" : "MANUAL");
    setReason("");
    setReference("");
    setDeciding({ row, approve });
  }

  const rows = queue.data ?? [];
  return (
    <div>
      <PageHeader eyebrow={t("nav.groups.payments")} title={t("nav.items.refunds")} subtitle={t("staff.refunds.subtitle")} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        {can("payment.view") && (
          <Card>
            <CardHeader title={t("staff.refunds.find")} subtitle={t("staff.refunds.findHint")} />
            <CardBody className="space-y-4">
              <form onSubmit={search} className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-sand-400" />
                  <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="260924-00182-7" className="pl-10 font-mono" data-testid="refund-code" data-scan-field="true" />
                </div>
                <Button type="submit" disabled={!code.trim()}>
                  {t("staff.teller.find")}
                </Button>
              </form>
              {order.isError && <Callout tone="danger">{t("errors.not_found")}</Callout>}
              {order.data && (
                <div data-testid="order-payments">
                  <div className="flex items-center justify-between">
                    <OrderCode code={order.data.order_code} />
                    <span className="text-[13px] text-sand-500">{order.data.patient_name}</span>
                  </div>
                  <ul className="mt-3 divide-y divide-sand-100 rounded-xl border border-sand-200">
                    {order.data.payments.length === 0 && <li className="p-4 text-center text-[13px] text-sand-500">{t("staff.refunds.noPayments")}</li>}
                    {order.data.payments.map((p) => (
                      <li key={p.id} className="flex items-center gap-3 p-3">
                        <div className="min-w-0 flex-1">
                          <div className="font-semibold tabular">
                            {formatMoney(p.amount, lang)} · {t(`enums.paymentMethod.${p.method}`)}
                            {p.method_hint ? ` (${p.method_hint})` : ""}
                          </div>
                          <div className="text-[12px] text-sand-500">
                            {formatDateTime(p.paid_at ?? p.created_at, lang)}
                            {p.bank_receipt_no ? ` · ${p.bank_receipt_no}` : ""}
                          </div>
                        </div>
                        <Badge tone={PAY_TONE[p.status] ?? "neutral"}>{t(`enums.paymentStatus.${p.status}`)}</Badge>
                        {p.status === "SUCCESS" && p.method !== "WAIVER" && can("payment.refund.request") && (
                          <Button size="sm" variant="outline" onClick={() => { setReason(""); setRequesting(p); }} data-testid="request-refund">
                            {t("staff.refunds.request")}
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardBody>
          </Card>
        )}
        <div>
          <div className="mb-3 flex justify-end">
            <SegmentedControl
              size="sm"
              value={status}
              onChange={setStatus}
              options={(["REQUESTED", "COMPLETED", "REJECTED", "FAILED"] as const).map((s) => ({ value: s, label: t(`enums.refundStatus.${s}`) }))}
            />
          </div>
          <Card>
            {rows.length === 0 && !queue.isLoading ? (
              <EmptyState icon={<HandCoins className="size-6" />} title={t("staff.refunds.empty")} />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <TH>{t("common.code")}</TH>
                    <TH>{t("common.reason")}</TH>
                    <TH className="text-right">{t("common.amount")}</TH>
                    <TH />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <TR key={r.id} data-testid="refund-row">
                      <TD>
                        <OrderCode code={r.order_code ?? ""} size="sm" />
                        <div className="text-[12px] text-sand-500">
                          {r.patient_name} · {formatRelative(r.created_at, lang)}
                        </div>
                      </TD>
                      <TD className="max-w-[16rem] text-[13px]">
                        {r.requested_by === null ? <Badge tone="warn">{t("staff.refunds.system")}</Badge> : null} {r.reason}
                        {r.status_reason && <div className="text-sand-500">→ {r.status_reason}</div>}
                        {r.manual_reference && <div className="text-sand-500">{r.manual_reference}</div>}
                      </TD>
                      <TD className="text-right tabular">{formatMoney(r.amount, lang)}</TD>
                      <TD className="text-right">
                        {(r.status === "REQUESTED" || r.status === "FAILED") && can("payment.refund.approve") && r.requested_by !== me?.id && (
                          <div className="flex justify-end gap-1.5">
                            <Button size="sm" onClick={() => openDecision(r, true)} data-testid="refund-approve">
                              {r.status === "FAILED" ? t("staff.refunds.retry") : t("staff.waivers.approve")}
                            </Button>
                            {r.status === "REQUESTED" && (
                              <Button size="sm" variant="ghost" onClick={() => openDecision(r, false)}>
                                {t("staff.waivers.decline")}
                              </Button>
                            )}
                          </div>
                        )}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        </div>
      </div>

      <Dialog
        open={!!requesting}
        onOpenChange={(v) => !v && setRequesting(null)}
        title={t("staff.refunds.request")}
        description={requesting ? formatMoney(requesting.amount, lang) : undefined}
        footer={
          <Button loading={request.isPending} disabled={reason.trim().length < 3} onClick={() => request.mutate()} data-testid="refund-submit">
            {t("common.confirm")}
          </Button>
        }
      >
        <Field label={t("common.reason")} hint={t("staff.refunds.twoPerson")}>
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} autoFocus data-testid="refund-reason" />
        </Field>
      </Dialog>

      <Dialog
        open={!!deciding}
        onOpenChange={(v) => !v && setDeciding(null)}
        title={deciding?.approve ? t("staff.refunds.approveTitle") : t("staff.refunds.rejectTitle")}
        description={deciding ? `${deciding.row.patient_name} · ${formatMoney(deciding.row.amount, lang)}` : undefined}
        footer={
          <Button
            variant={deciding?.approve ? "primary" : "danger"}
            loading={decide.isPending}
            disabled={deciding?.approve ? mode === "MANUAL" && !reference.trim() : reason.trim().length < 3}
            onClick={() => decide.mutate()}
            data-testid="refund-confirm"
          >
            {deciding?.approve ? t("staff.waivers.approve") : t("staff.waivers.decline")}
          </Button>
        }
      >
        <div className="space-y-4">
          {deciding?.approve ? (
            <>
              <Field label={t("staff.refunds.mode")}>
                <Select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)} disabled={deciding.row.payment_method !== "GATEWAY"}>
                  <option value="MANUAL">{t("staff.refunds.modeManual")}</option>
                  {deciding.row.payment_method === "GATEWAY" && <option value="PROVIDER">{t("staff.refunds.modeProvider")}</option>}
                </Select>
              </Field>
              {mode === "MANUAL" && (
                <Field label={t("staff.refunds.reference")} hint={t("staff.refunds.referenceHint")} required>
                  <Input value={reference} onChange={(e) => setReference(e.target.value)} data-testid="refund-reference" autoFocus />
                </Field>
              )}
            </>
          ) : (
            <Field label={t("common.reason")}>
              <Textarea value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
            </Field>
          )}
        </div>
      </Dialog>
    </div>
  );
}

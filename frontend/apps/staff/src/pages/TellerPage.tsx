import { isApiError, unwrap, type Schemas } from "@bmu/api-client";
import { formatDateTime, formatMoney, formatTime, useI18n } from "@bmu/i18n";
import {
  Badge,
  Button,
  Card,
  CardBody,
  cn,
  Dialog,
  Field,
  Input,
  OrderCode,
  PageHeader,
  Table,
  TD,
  TH,
  TR,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, BadgeCheck, CheckCircle2, Clock, FileClock, Printer, ScanLine, Search, XCircle } from "lucide-react";
import { useRef, useState, type FormEvent, type ReactNode } from "react";

import { api, printPdf } from "../lib/api";
import { errorMessage, useErrorToast } from "../lib/errors";

type Lookup = Schemas["LookupOut"];
type Receipt = Schemas["ReceiptOut"];
type Method = "BANK_TELLER" | "COUNTER_CASH";

const STATE_STYLE: Record<Lookup["state"], { tone: string; icon: ReactNode }> = {
  RECEIVABLE: { tone: "border-brand-300 bg-brand-50", icon: <BadgeCheck className="size-10 text-brand-600" /> },
  ALREADY_PAID: { tone: "border-danger-600 bg-danger-50", icon: <AlertOctagon className="size-10 text-danger-600" /> },
  NOT_VERIFIED: { tone: "border-warn-600 bg-warn-50", icon: <Clock className="size-10 text-warn-600" /> },
  EXPIRED: { tone: "border-sand-300 bg-sand-100", icon: <FileClock className="size-10 text-sand-500" /> },
  CLOSED: { tone: "border-sand-300 bg-sand-100", icon: <XCircle className="size-10 text-sand-500" /> },
};

/** Bank teller (ROADMAP §5.2) and hospital cashier: scan or type the code → name, code and amount →
 *  "Received" → PAID → token printed. The same screen serves both; `method` selects the payment type. */
export default function TellerPage({ method = "BANK_TELLER" }: { method?: Method }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const input = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [lookup, setLookup] = useState<Lookup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiptNo, setReceiptNo] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [dayClose, setDayClose] = useState(false);

  const printToken = useMutation({
    mutationFn: (tokenId: string) => printPdf(`/api/v1/staff/tokens/${tokenId}/print`, "POST"),
    onError,
  });

  const find = useMutation({
    mutationFn: (value: string) =>
      unwrap(api.GET("/api/v1/staff/payments/lookup/{ref}", { params: { path: { ref: value } } })),
    onSuccess: (out) => {
      setLookup(out);
      setError(null);
      setReceipt(null);
    },
    onError: (e) => {
      setLookup(null);
      setError(isApiError(e) && e.code === "CODE_MISTYPED" ? t("errors.code_mistyped") : errorMessage(t, e));
    },
  });

  const receive = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/staff/payments/receive/{ref}", {
          params: { path: { ref: lookup!.order_code } },
          body: { method, receipt_no: receiptNo.trim() || null },
        }),
      ),
    onSuccess: (out) => {
      setReceipt(out);
      setLookup(null);
      setCode("");
      setReceiptNo("");
      void qc.invalidateQueries({ queryKey: ["day-close"] });
      printToken.mutate(out.token.id);
    },
    onError: (e) => {
      // someone else paid in the meantime: show the fresh state instead of a toast
      if (isApiError(e) && e.code === "ORDER_ALREADY_PAID" && lookup) find.mutate(lookup.order_code);
      else onError(e);
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (code.trim()) find.mutate(code.trim());
  }

  function reset() {
    setReceipt(null);
    setLookup(null);
    setError(null);
    setCode("");
    input.current?.focus();
  }

  const needReceipt = method === "BANK_TELLER" && !!lookup?.receipt_no_required;
  const title = method === "BANK_TELLER" ? t("staff.teller.title") : t("staff.teller.cashierTitle");

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        eyebrow={t("nav.groups.payments")}
        title={title}
        subtitle={t(method === "BANK_TELLER" ? "staff.teller.subtitle" : "staff.teller.cashierSubtitle")}
        actions={
          <Button variant="outline" icon={<Printer className="size-4" />} onClick={() => setDayClose(true)}>
            {t("staff.teller.dayClose")}
          </Button>
        }
      />

      {receipt ? (
        <Card className="overflow-hidden">
          <div className="flex flex-col items-center bg-brand-950 px-6 py-10 text-center text-white" data-testid="receipt">
            <CheckCircle2 className="size-12 text-brand-300" />
            <p className="mt-3 text-[13px] font-semibold uppercase tracking-[0.14em] text-white/50">{t("staff.teller.received")}</p>
            <p className="mt-1 text-4xl font-bold tabular">{formatMoney(receipt.amount, lang)}</p>
            <p className="mt-1 text-[15px] text-white/80">{receipt.patient_name}</p>
            <div className="mt-6 rounded-3xl bg-white px-10 py-5 text-ink">
              <p className="text-[12px] font-semibold uppercase tracking-wider text-sand-500">{t("staff.teller.token")}</p>
              <p className="font-mono text-6xl font-extrabold tracking-wide" data-testid="token-label">
                {receipt.token.label}
              </p>
            </div>
            <div className="mt-4">
              <OrderCode code={receipt.order_code} size="md" tone="inverse" />
            </div>
          </div>
          <CardBody className="flex flex-wrap gap-2">
            <Button icon={<Printer className="size-4" />} loading={printToken.isPending} onClick={() => printToken.mutate(receipt.token.id)}>
              {t("staff.teller.printToken")}
            </Button>
            <Button variant="secondary" className="ml-auto" onClick={reset} data-testid="teller-next">
              {t("staff.teller.next")}
            </Button>
          </CardBody>
        </Card>
      ) : (
        <>
          <form onSubmit={submit}>
            <div className="relative">
              <ScanLine className="pointer-events-none absolute left-5 top-1/2 size-6 -translate-y-1/2 text-brand-600" />
              <Input
                ref={input}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={t("staff.teller.scanPlaceholder")}
                inputSize="xl"
                className="pl-14 font-mono"
                autoFocus
                data-scan-field="true"
                data-testid="teller-code"
                autoComplete="off"
                inputMode="numeric"
              />
            </div>
            <div className="mt-3 flex justify-end">
              <Button type="submit" icon={<Search className="size-4" />} loading={find.isPending} disabled={!code.trim()}>
                {t("staff.teller.find")}
              </Button>
            </div>
          </form>

          {error && (
            <Card className="mt-4 border-danger-600 bg-danger-50">
              <CardBody className="text-[15px] font-semibold text-danger-700" data-testid="teller-error">
                {error}
              </CardBody>
            </Card>
          )}

          {lookup && (
            <Card className={cn("mt-5 border-2", STATE_STYLE[lookup.state].tone)} data-testid="lookup-card" data-state={lookup.state}>
              <CardBody className="space-y-5">
                <div className="flex items-start gap-4">
                  {STATE_STYLE[lookup.state].icon}
                  <div className="min-w-0 flex-1">
                    <div className="text-2xl font-bold">{t(`staff.teller.states.${lookup.state}`)}</div>
                    <p className="mt-0.5 text-[14px] text-sand-700">{t(`staff.teller.stateHints.${lookup.state}`)}</p>
                  </div>
                </div>

                <div className="grid gap-4 rounded-2xl bg-white p-5 ring-1 ring-sand-200 sm:grid-cols-[1fr_auto]">
                  <div className="min-w-0">
                    <OrderCode code={lookup.order_code} size="lg" />
                    <div className="mt-2 text-xl font-semibold" data-testid="lookup-name">{lookup.patient_name}</div>
                    <div className="text-[13px] text-sand-500">
                      {lookup.patient_age ?? "—"} · {lookup.tests.join(", ")}
                    </div>
                    {lookup.priority !== "NORMAL" && <Badge tone="danger" className="mt-2">{t(`enums.priority.${lookup.priority}`)}</Badge>}
                  </div>
                  <div className="sm:text-right">
                    <div className="text-[12px] font-semibold uppercase tracking-wider text-sand-500">
                      {lookup.state === "ALREADY_PAID" ? t("staff.teller.paidAmount") : t("staff.teller.amountDue")}
                    </div>
                    <div className="text-5xl font-extrabold tabular" data-testid="lookup-amount">
                      {formatMoney(lookup.state === "ALREADY_PAID" ? (lookup.paid?.amount ?? lookup.total) : lookup.amount_due || lookup.total, lang)}
                    </div>
                    {lookup.discount > 0 && (
                      <div className="text-[13px] text-ok-600">
                        {t("staff.orderDetail.discount")} −{formatMoney(lookup.discount, lang)}
                      </div>
                    )}
                  </div>
                </div>

                {lookup.state === "ALREADY_PAID" && (
                  <div className="rounded-2xl bg-white p-4 text-[15px] ring-1 ring-danger-100" data-testid="already-paid">
                    {lookup.paid && (
                      <p>
                        {t("staff.teller.paidVia", {
                          method: t(`enums.paymentMethod.${lookup.paid.method}`),
                          at: formatDateTime(lookup.paid.paid_at, lang),
                        })}
                      </p>
                    )}
                    {lookup.token && (
                      <p className="mt-1">
                        {t("staff.teller.token")}: <b className="font-mono">{lookup.token.label}</b>{" "}
                        <Button size="sm" variant="outline" className="ml-2" onClick={() => printToken.mutate(lookup.token!.id)}>
                          {t("common.reprint")}
                        </Button>
                      </p>
                    )}
                  </div>
                )}

                {lookup.state === "RECEIVABLE" && (
                  <div className="space-y-3">
                    {needReceipt && (
                      <Field label={t("staff.teller.receiptNo")} required>
                        <Input value={receiptNo} onChange={(e) => setReceiptNo(e.target.value)} data-testid="receipt-no" autoFocus />
                      </Field>
                    )}
                    {method === "BANK_TELLER" && !needReceipt && (
                      <Field label={t("staff.teller.receiptNo")} hint={t("common.optional")}>
                        <Input value={receiptNo} onChange={(e) => setReceiptNo(e.target.value)} data-testid="receipt-no" />
                      </Field>
                    )}
                    <Button
                      block
                      size="xl"
                      icon={<CheckCircle2 className="size-5" />}
                      loading={receive.isPending}
                      disabled={needReceipt && !receiptNo.trim()}
                      onClick={() => receive.mutate()}
                      data-testid="receive"
                    >
                      {t("staff.teller.receive", { amount: formatMoney(lookup.amount_due, lang) })}
                    </Button>
                    {method === "COUNTER_CASH" && !lookup.counter_enabled && (
                      <p className="text-[13px] text-danger-700">{t("staff.teller.counterOff")}</p>
                    )}
                  </div>
                )}
              </CardBody>
            </Card>
          )}
        </>
      )}
      <DayClose open={dayClose} onOpenChange={setDayClose} />
    </div>
  );
}

function DayClose({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { t, lang } = useI18n();
  const close = useQuery({
    queryKey: ["day-close"],
    queryFn: () => unwrap(api.GET("/api/v1/staff/payments/day-close", { params: { query: {} } })),
    enabled: open,
  });
  const d = close.data;
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      size="lg"
      title={t("staff.teller.dayClose")}
      description={d ? `${d.staff_name} · ${formatDateTime(`${d.day}T00:00:00+06:00`, lang)}${d.station ? ` · ${d.station}` : ""}` : undefined}
      footer={
        <Button icon={<Printer className="size-4" />} onClick={() => window.print()}>
          {t("common.print")}
        </Button>
      }
    >
      {d && (
        <div className="space-y-4" data-testid="day-close">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-sand-50 p-3">
              <div className="text-[12px] text-sand-500">{t("staff.teller.count")}</div>
              <div className="text-2xl font-bold tabular" data-testid="dc-count">{d.count}</div>
            </div>
            <div className="rounded-xl bg-sand-50 p-3">
              <div className="text-[12px] text-sand-500">{t("common.total")}</div>
              <div className="text-2xl font-bold tabular" data-testid="dc-total">{formatMoney(d.total, lang)}</div>
            </div>
            <div className="rounded-xl bg-sand-50 p-3">
              <div className="text-[12px] text-sand-500">{t("staff.teller.net")}</div>
              <div className="text-2xl font-bold tabular">{formatMoney(d.net, lang)}</div>
              {d.refunded_total > 0 && <div className="text-[11px] text-danger-600">−{formatMoney(d.refunded_total, lang)}</div>}
            </div>
          </div>
          <Table>
            <thead>
              <tr>
                <TH>{t("common.time")}</TH>
                <TH>{t("common.code")}</TH>
                <TH>{t("staff.teller.receiptNo")}</TH>
                <TH>{t("staff.teller.token")}</TH>
                <TH className="text-right">{t("common.amount")}</TH>
              </tr>
            </thead>
            <tbody>
              {d.rows.map((r) => (
                <TR key={r.payment_id} className={r.status === "REFUNDED" ? "opacity-50 line-through" : ""}>
                  <TD className="tabular text-[13px]">{formatTime(r.paid_at, lang)}</TD>
                  <TD>
                    <OrderCode code={r.order_code ?? ""} size="sm" />
                  </TD>
                  <TD className="text-[13px]">{r.receipt_no ?? "—"}</TD>
                  <TD className="font-mono text-[13px]">{r.token ?? "—"}</TD>
                  <TD className="text-right tabular">{formatMoney(r.amount, lang)}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
          {d.rows.length === 0 && <p className="py-4 text-center text-[13px] text-sand-500">{t("staff.teller.noPayments")}</p>}
        </div>
      )}
    </Dialog>
  );
}

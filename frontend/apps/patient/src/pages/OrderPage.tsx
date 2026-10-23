import { unwrap, type Schemas } from "@bmu/api-client";
import { formatDateTime, formatMoney, useI18n } from "@bmu/i18n";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardBody,
  compressImage,
  EmptyState,
  Field,
  OrderCode,
  QrCode,
  Skeleton,
  Textarea,
  Timeline,
  toast,
  type Tone,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, MessageCircleQuestion, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { Screen } from "../components/Layout";
import { api, loadOffline, upload } from "../lib/api";
import { useErrorToast } from "../lib/errors";

const TONES: Record<string, Tone> = {
  PENDING_VERIFICATION: "info",
  NEEDS_CLARIFICATION: "warn",
  AWAITING_PAYMENT: "violet",
  PAID: "ok",
  REJECTED: "danger",
  CANCELLED: "neutral",
  EXPIRED: "neutral",
  COMPLETED: "ok",
};

export function StatusPill({ status }: { status: string }) {
  const { t } = useI18n();
  return (
    <Badge tone={TONES[status] ?? "brand"} dot>
      {t(`enums.orderStatus.${status}`)}
    </Badge>
  );
}

function Clarify({ order }: { order: Schemas["OrderOut"] }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const send = useMutation({
    mutationFn: async () => {
      if (files.length) {
        const form = new FormData();
        for (const f of files) form.append("files", await compressImage(f));
        await upload(`/api/v1/patient/orders/${order.id}/prescription-images`, form);
      }
      return unwrap(
        api.POST("/api/v1/patient/orders/{order_id}/clarification", {
          params: { path: { order_id: order.id } },
          body: { note: note.trim() || null },
        }),
      );
    },
    onSuccess: () => {
      toast.success(t("patient.order.clarifySent"));
      void qc.invalidateQueries({ queryKey: ["order"] });
    },
    onError,
  });
  const room = 3 - (order.prescription?.image_count ?? 0);
  return (
    <Card className="border-warn-100 bg-warn-50/60">
      <CardBody className="space-y-3">
        <div className="flex items-start gap-3">
          <MessageCircleQuestion className="mt-0.5 size-5 shrink-0 text-warn-700" />
          <div>
            <div className="font-semibold text-warn-700">{t("patient.order.clarifyTitle")}</div>
            <p className="mt-1 text-[15px]">{order.clarification_note}</p>
          </div>
        </div>
        {room > 0 && (
          <label className="flex h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-warn-600/40 bg-white text-[15px] font-semibold text-warn-700">
            <Camera className="size-5" />
            {files.length ? t("patient.order.photosAdded", { count: files.length }) : t("patient.order.addPhoto")}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              className="sr-only"
              onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, room))}
            />
          </label>
        )}
        <Field label={t("patient.order.reply")}>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} className="min-h-20 bg-white" />
        </Field>
        <Button block size="lg" loading={send.isPending} disabled={!note.trim() && !files.length} onClick={() => send.mutate()}>
          {t("patient.order.sendReply")}
        </Button>
      </CardBody>
    </Card>
  );
}

const METHODS = ["bkash", "nagad", "upay", "rocket", "card"] as const;
const METHOD_STYLE: Record<(typeof METHODS)[number], string> = {
  bkash: "bg-[#e2136e] text-white",
  nagad: "bg-[#f6921e] text-white",
  upay: "bg-[#ffc20e] text-ink",
  rocket: "bg-[#8c3494] text-white",
  card: "bg-ink text-white",
};

/** Amount due, online payment methods (when enabled) and the "pay at hospital" alternative (ROADMAP §5.1/5.3). */
function PayCard({ order }: { order: Schemas["OrderOut"] }) {
  const { t, lang } = useI18n();
  const onError = useErrorToast();
  const config = useQuery({
    queryKey: ["pay-config"],
    queryFn: () => unwrap(api.GET("/api/v1/public/payments/config")),
    staleTime: 5 * 60_000,
  });
  const pay = useMutation({
    mutationFn: (method: (typeof METHODS)[number]) =>
      unwrap(api.POST("/api/v1/patient/orders/{order_id}/pay", { params: { path: { order_id: order.id } }, body: { method } })),
    onSuccess: (out) => {
      window.location.assign(out.redirect_url);
    },
    onError,
  });
  return (
    <Card className="mt-4 border-violet-600/20">
      <CardBody className="space-y-4">
        <div className="flex items-start gap-3">
          <Wallet className="mt-0.5 size-5 shrink-0 text-violet-600" />
          <div>
            <div className="text-[17px] font-bold" data-testid="amount-due">
              {t("patient.order.payTitle", { amount: formatMoney(order.amount_due, lang) })}
            </div>
            <p className="mt-0.5 text-[14px] text-sand-600">{t("patient.pay.choose")}</p>
          </div>
        </div>
        {config.data?.online_payments && (
          <div className="grid grid-cols-2 gap-2.5">
            {METHODS.filter((m) => config.data?.methods.includes(m)).map((m) => (
              <button
                key={m}
                type="button"
                disabled={pay.isPending}
                onClick={() => pay.mutate(m)}
                data-testid={`pay-${m}`}
                className={`${METHOD_STYLE[m]} h-14 rounded-2xl text-[16px] font-bold shadow-card transition active:scale-[0.98] disabled:opacity-60 ${m === "card" ? "col-span-2" : ""}`}
              >
                {t(`patient.pay.methods.${m}`)}
              </button>
            ))}
          </div>
        )}
        <div className="rounded-2xl bg-sand-50 p-4 ring-1 ring-sand-200" data-testid="pay-at-hospital">
          <div className="font-semibold">{t("patient.pay.atHospital")}</div>
          <p className="mt-1 text-[14px] text-sand-600">{t("patient.pay.atHospitalBody")}</p>
          <div className="mt-2">
            <OrderCode code={order.order_code ?? ""} size="lg" />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

/** Order status, code + QR, progress timeline, tests with price and preparation (ROADMAP M3). */
export default function OrderPage() {
  const { ref = "" } = useParams();
  const [params] = useSearchParams();
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const order = useQuery({
    queryKey: ["order", ref],
    queryFn: () => unwrap(api.GET("/api/v1/patient/orders/{ref}", { params: { path: { ref } } })),
    retry: false,
    refetchInterval: 30_000,
  });
  const cancel = useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/patient/orders/{order_id}/cancel", { params: { path: { order_id: id } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["order"] }),
    onError,
  });
  const [justSubmitted, setJustSubmitted] = useState(params.get("new") === "1");
  useEffect(() => {
    if (!justSubmitted) return;
    const id = window.setTimeout(() => setJustSubmitted(false), 8000);
    return () => window.clearTimeout(id);
  }, [justSubmitted]);

  const o = order.data ?? loadOffline().find((x) => x.id === ref || x.order_code === ref.replace(/\D/g, ""));
  if (order.isLoading && !o) return <Screen back="/orders"><Skeleton className="mt-4 h-96" /></Screen>;
  if (!o) {
    return (
      <Screen back="/orders">
        <EmptyState title={t("errors.not_found")} />
      </Screen>
    );
  }
  const cancellable = ["PENDING_VERIFICATION", "NEEDS_CLARIFICATION", "AWAITING_PAYMENT"].includes(o.status);

  return (
    <Screen back="/orders" title={o.patient.full_name}>
      {justSubmitted && (
        <Callout tone="ok" icon={<CheckCircle2 className="size-5" />} className="mb-4 mt-2" title={t("patient.order.submittedTitle")}>
          {t("patient.order.submittedBody")}
        </Callout>
      )}
      <Card className="mt-2 overflow-hidden">
        <div className="flex items-center gap-4 bg-brand-950 p-5 text-white">
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-semibold uppercase tracking-[0.14em] text-white/50">{t("patient.order.code")}</div>
            <div data-testid="order-code">
              <OrderCode code={o.order_code ?? ""} size="lg" tone="inverse" />
            </div>
            <div className="mt-2">
              <StatusPill status={o.status} />
            </div>
          </div>
          {o.order_code && <QrCode value={o.order_code} size={92} />}
        </div>
        <CardBody>
          <Timeline
            steps={o.timeline.map((s) => ({
              key: s.key,
              state: s.state,
              title: t(`enums.timeline.${s.key}`),
              detail:
                s.key === "verified" && s.state === "current" && o.sla_due_at
                  ? t("patient.order.verifyBy", { time: formatDateTime(o.sla_due_at, lang) })
                  : (s.note ?? undefined),
              at: s.at ? formatDateTime(s.at, lang) : undefined,
            }))}
          />
        </CardBody>
      </Card>

      {o.status === "NEEDS_CLARIFICATION" && (
        <div className="mt-4">
          <Clarify order={o} />
        </div>
      )}
      {o.status === "REJECTED" && (
        <Callout tone="danger" className="mt-4" title={t("patient.order.rejectedTitle")}>
          {o.status_reason}
        </Callout>
      )}
      {o.status === "AWAITING_PAYMENT" && <PayCard order={o} />}
      {o.status === "PAID" && (
        <Callout tone="ok" icon={<CheckCircle2 className="size-5" />} className="mt-4" title={t("patient.order.paidTitle")}>
          {t("patient.order.paidBody")}
        </Callout>
      )}

      <Card className="mt-4">
        <ul className="divide-y divide-sand-100">
          {o.items.map((i) => {
            const prep = lang === "bn" ? i.prep_bn : i.prep_en;
            return (
              <li key={i.id} className="px-4 py-3.5" data-testid="order-item">
                <div className="flex items-start gap-3">
                  <span className="min-w-0 flex-1 font-semibold">{lang === "bn" ? i.test_name_bn : i.test_name_en}</span>
                  <span className="tabular" data-testid="item-price">{formatMoney(i.price_snapshot, lang)}</span>
                </div>
                {i.fasting_required && (
                  <Badge tone="warn" className="mt-1.5">
                    {t("patient.book.fastingHours", { hours: i.fasting_hours ?? "?" })}
                  </Badge>
                )}
                {prep && <p className="mt-1.5 text-[13.5px] text-sand-600" data-testid="item-prep">{prep}</p>}
              </li>
            );
          })}
          {o.discount > 0 && (
            <li className="flex justify-between px-4 py-3 text-ok-600">
              <span>{t("patient.order.waiver")}</span>
              <span className="tabular">−{formatMoney(o.discount, lang)}</span>
            </li>
          )}
          <li className="flex items-center justify-between bg-sand-50 px-4 py-3 font-bold">
            <span>{t("common.total")}</span>
            <span className="text-[18px] tabular" data-testid="order-total">{formatMoney(o.total, lang)}</span>
          </li>
        </ul>
      </Card>
      {o.status === "PENDING_VERIFICATION" && <p className="mt-3 text-[13px] text-sand-500">{t("patient.book.priceNote")}</p>}
      {cancellable && (
        <Button variant="ghost" block className="mt-6 text-danger-600" loading={cancel.isPending} onClick={() => window.confirm(t("patient.order.cancelConfirm")) && cancel.mutate(o.id)}>
          {t("patient.order.cancel")}
        </Button>
      )}
    </Screen>
  );
}

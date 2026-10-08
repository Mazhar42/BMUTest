import { unwrap } from "@bmu/api-client";
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
  Skeleton,
  Textarea,
  toast,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, FileX2, MessageCircleQuestion } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ImageViewer } from "../components/ImageViewer";
import { patientLine } from "../components/PatientFinder";
import { OrderStatusBadge, PriorityBadge } from "../components/StatusBadge";
import { TestPicker, type PickedTest } from "../components/TestPicker";
import { api } from "../lib/api";
import { useErrorToast } from "../lib/errors";

export default function VerifyOrderPage() {
  const { orderId = "" } = useParams();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [tests, setTests] = useState<PickedTest[]>([]);
  const [dialog, setDialog] = useState<"clarify" | "reject" | null>(null);
  const [reason, setReason] = useState("");

  const order = useQuery({
    queryKey: ["order", orderId],
    queryFn: () => unwrap(api.GET("/api/v1/staff/orders/{ref}", { params: { path: { ref: orderId } } })),
  });

  useEffect(() => {
    if (!order.data) return;
    setTests(
      order.data.items.map((i) => ({
        id: i.test_id,
        code: i.test_code,
        name_en: i.test_name_en,
        name_bn: i.test_name_bn,
        abbreviation: i.abbreviation,
        price: i.price_snapshot,
      })),
    );
  }, [order.data]);

  const done = (key: string) => {
    toast.success(t(key));
    void qc.invalidateQueries({ queryKey: ["verification-queue"] });
    void qc.invalidateQueries({ queryKey: ["order-stats"] });
    navigate("/verification");
  };

  const original = new Set(order.data?.items.map((i) => i.test_id) ?? []);
  const edited = tests.length !== original.size || tests.some((x) => !original.has(x.id));

  const confirm = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/staff/orders/{order_id}/verify", {
          params: { path: { order_id: orderId } },
          body: { test_ids: edited ? tests.map((x) => x.id) : null },
        }),
      ),
    onSuccess: () => done("staff.verify.confirmed"),
    onError,
  });
  const decide = useMutation({
    mutationFn: (kind: "clarify" | "reject") =>
      unwrap(
        api.POST(kind === "clarify" ? "/api/v1/staff/orders/{order_id}/clarify" : "/api/v1/staff/orders/{order_id}/reject", {
          params: { path: { order_id: orderId } },
          body: { reason: reason.trim() },
        }),
      ),
    onSuccess: (_, kind) => done(kind === "clarify" ? "staff.verify.clarifySent" : "staff.verify.rejected"),
    onError,
  });

  if (order.isLoading) return <Skeleton className="h-[520px]" />;
  const o = order.data;
  if (!o) return <EmptyState title={t("errors.not_found")} />;
  const pending = o.status === "PENDING_VERIFICATION";

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Link to="/verification" className="rounded-lg p-2 text-sand-500 hover:bg-sand-100" aria-label={t("common.back")}>
          <ArrowLeft className="size-5" />
        </Link>
        <OrderCode code={o.order_code ?? ""} size="lg" />
        <OrderStatusBadge status={o.status} />
        <PriorityBadge priority={o.priority} />
        {o.overdue && <Badge tone="danger">{t("staff.verify.overdue")}</Badge>}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="min-h-[480px]">
          {o.prescription ? (
            <ImageViewer prescriptionId={o.prescription.id} pages={o.prescription.image_count} />
          ) : (
            <Card className="h-full">
              <EmptyState icon={<FileX2 className="size-6" />} title={t("staff.verify.noPrescription")} />
            </Card>
          )}
        </div>
        <div className="space-y-5">
          <Card>
            <CardHeader
              title={o.patient.full_name}
              subtitle={`${patientLine(o.patient, t)} · ${t(`enums.channel.${o.channel}`)} · ${formatDateTime(o.submitted_at, lang)}`}
            />
            {(o.notes || o.prescription?.doctor_name) && (
              <CardBody className="space-y-1 text-[14px]">
                {o.prescription?.doctor_name && (
                  <div>
                    <span className="text-sand-500">{t("staff.helpdesk.doctor")}: </span>
                    {o.prescription.doctor_name}
                  </div>
                )}
                {o.notes && (
                  <div>
                    <span className="text-sand-500">{t("staff.verify.patientNote")}: </span>
                    {o.notes}
                  </div>
                )}
              </CardBody>
            )}
          </Card>
          <Card>
            <CardHeader title={t("staff.verify.tests")} subtitle={t("staff.verify.testsHint")} />
            <CardBody>
              <TestPicker value={tests} onChange={setTests} />
              {edited && (
                <Callout tone="warn" className="mt-3">
                  {t("staff.verify.edited")}
                </Callout>
              )}
            </CardBody>
          </Card>
          {pending ? (
            <div className="flex flex-wrap gap-2">
              <Button
                size="lg"
                icon={<Check className="size-4" />}
                loading={confirm.isPending}
                disabled={tests.length === 0}
                onClick={() => confirm.mutate()}
                data-testid="verify-confirm"
              >
                {t("staff.verify.confirm")} · {formatMoney(tests.reduce((s, x) => s + (x.price ?? 0), 0), lang)}
              </Button>
              <Button size="lg" variant="outline" icon={<MessageCircleQuestion className="size-4" />} onClick={() => setDialog("clarify")}>
                {t("staff.verify.clarify")}
              </Button>
              <Button size="lg" variant="ghost" className="text-danger-600" onClick={() => setDialog("reject")}>
                {t("staff.verify.reject")}
              </Button>
            </div>
          ) : (
            <Callout tone="info">{t("staff.verify.notPending")}</Callout>
          )}
        </div>
      </div>
      <Dialog
        open={dialog !== null}
        onOpenChange={(v) => !v && setDialog(null)}
        title={dialog === "reject" ? t("staff.verify.rejectTitle") : t("staff.verify.clarifyTitle")}
        description={dialog === "reject" ? t("staff.verify.rejectHint") : t("staff.verify.clarifyHint")}
        tone={dialog === "reject" ? "danger" : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant={dialog === "reject" ? "danger" : "primary"}
              loading={decide.isPending}
              disabled={reason.trim().length < 3}
              onClick={() => dialog && decide.mutate(dialog)}
            >
              {dialog === "reject" ? t("staff.verify.reject") : t("staff.verify.sendClarify")}
            </Button>
          </>
        }
      >
        <Field label={t("common.reason")} hint={t("staff.verify.smsNote")}>
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
        </Field>
      </Dialog>
    </div>
  );
}

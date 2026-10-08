import { unwrap, type Schemas } from "@bmu/api-client";
import { formatMoney, useI18n } from "@bmu/i18n";
import {
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  compressImage,
  Field,
  Input,
  OrderCode,
  PageHeader,
  Select,
  Textarea,
  toast,
} from "@bmu/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, FileImage, Printer, RotateCcw, UserRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { PatientFinder, patientLine, type StaffPatient } from "../components/PatientFinder";
import { TestPicker, type PickedTest } from "../components/TestPicker";
import { api, printPdf, upload } from "../lib/api";
import { useErrorToast } from "../lib/errors";

const FEE_CATEGORIES = ["GENERAL", "FREE", "POOR_FUND", "STAFF", "CONCESSION"] as const;
const PRIORITIES = ["NORMAL", "ELDERLY", "DISABLED", "EMERGENCY"] as const;

/** Walk-in order (ROADMAP §5.2): find/register → tests against the paper prescription → inline
 *  verification → AWAITING_PAYMENT → 3-part slip. */
export default function HelpDeskPage() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [params] = useSearchParams();
  const [patient, setPatient] = useState<StaffPatient | null>(null);
  const [tests, setTests] = useState<PickedTest[]>([]);
  const [photos, setPhotos] = useState<File[]>([]);
  const [doctor, setDoctor] = useState("");
  const [fee, setFee] = useState<(typeof FEE_CATEGORIES)[number]>("GENERAL");
  const [priority, setPriority] = useState<(typeof PRIORITIES)[number]>("NORMAL");
  const [waiverReason, setWaiverReason] = useState("");
  const [smsLang, setSmsLang] = useState<"bn" | "en">("bn");
  const [created, setCreated] = useState<Schemas["StaffOrderOut"] | null>(null);
  const preselect = params.get("patient");

  // Arriving from the patient screen ("New order"): start with that patient selected.
  useEffect(() => {
    if (!preselect) return;
    void unwrap(api.GET("/api/v1/staff/patients/{patient_id}", { params: { path: { patient_id: preselect } } }))
      .then(setPatient)
      .catch(onError);
  }, [preselect, onError]);

  const print = useMutation({
    mutationFn: (orderId: string) => printPdf(`/api/v1/staff/orders/${orderId}/slip`, "POST"),
    onError,
  });

  const create = useMutation({
    mutationFn: async () => {
      if (!patient) throw new Error("no patient");
      let prescriptionId: string | null = null;
      if (photos.length) {
        const form = new FormData();
        form.append("patient_id", patient.id);
        if (doctor.trim()) form.append("doctor_name", doctor.trim());
        for (const f of photos) form.append("files", await compressImage(f));
        prescriptionId = (await upload<Schemas["PrescriptionOut"]>("/api/v1/staff/prescriptions", form)).id;
      }
      return unwrap(
        api.POST("/api/v1/staff/orders/walkin", {
          body: {
            patient_id: patient.id,
            test_ids: tests.map((x) => x.id),
            prescription_id: prescriptionId,
            priority,
            fee_category: fee,
            waiver_reason: fee === "GENERAL" ? null : waiverReason.trim(),
            lang: smsLang,
          },
        }),
      );
    },
    onSuccess: (order) => {
      setCreated(order);
      void qc.invalidateQueries({ queryKey: ["order-stats"] });
      toast.success(t("staff.helpdesk.created"));
      print.mutate(order.id);
    },
    onError,
  });

  function reset() {
    setPatient(null);
    setTests([]);
    setPhotos([]);
    setDoctor("");
    setFee("GENERAL");
    setPriority("NORMAL");
    setWaiverReason("");
    setCreated(null);
  }

  if (created) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card className="overflow-hidden">
          <div className="flex flex-col items-center bg-brand-950 px-6 py-10 text-center text-white">
            <CheckCircle2 className="size-10 text-brand-300" />
            <p className="mt-3 text-[13px] font-semibold uppercase tracking-[0.14em] text-white/50">{t("staff.helpdesk.orderCode")}</p>
            <div data-testid="created-code">
              <OrderCode code={created.order_code ?? ""} size="xl" tone="inverse" />
            </div>
            <p className="mt-3 text-[15px] text-white/80">
              {created.patient.full_name} · {formatMoney(created.total, lang)}
            </p>
          </div>
          <CardBody className="space-y-3">
            <Callout tone={created.waivers.length ? "warn" : "info"}>
              {created.waivers.length ? t("staff.helpdesk.waiverPending") : t("staff.helpdesk.nextBank")}
            </Callout>
            <div className="flex flex-wrap gap-2">
              <Button icon={<Printer className="size-4" />} loading={print.isPending} onClick={() => print.mutate(created.id)}>
                {t("common.reprint")}
              </Button>
              <Link to={`/orders/${created.order_code}`} className="inline-flex">
                <Button variant="outline">{t("staff.helpdesk.openOrder")}</Button>
              </Link>
              <Button variant="secondary" icon={<RotateCcw className="size-4" />} onClick={reset} className="ml-auto">
                {t("staff.helpdesk.next")}
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  const canCreate = !!patient && tests.length > 0 && (fee === "GENERAL" || waiverReason.trim().length >= 3);
  const total = tests.reduce((s, x) => s + (x.price ?? 0), 0);

  return (
    <div>
      <PageHeader eyebrow={t("nav.groups.frontDesk")} title={t("nav.items.helpdesk")} subtitle={t("staff.helpdesk.subtitle")} />
      <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <Card>
            <CardHeader icon={<UserRound className="size-4" />} title={t("staff.helpdesk.step1")} />
            <CardBody>
              {patient ? (
                <div className="flex items-center gap-3 rounded-xl bg-brand-50/60 px-4 py-3 ring-1 ring-brand-100">
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-semibold" data-testid="picked-patient">{patient.full_name}</span>
                    <span className="block text-[13px] text-sand-600">{patientLine(patient, t)}</span>
                  </span>
                  <Button size="sm" variant="ghost" onClick={() => setPatient(null)}>
                    {t("staff.helpdesk.change")}
                  </Button>
                </div>
              ) : (
                <PatientFinder onPick={setPatient} initialQuery={params.get("q") ?? ""} />
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader icon={<FileImage className="size-4" />} title={t("staff.helpdesk.step2")} subtitle={t("staff.helpdesk.step2Hint")} />
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <Field label={t("staff.helpdesk.photo")} hint={t("staff.helpdesk.photoHint")}>
                <label className="flex h-10 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-sand-300 bg-white px-3.5 text-[14px] text-sand-600 hover:border-brand-400">
                  <Camera className="size-4" />
                  {photos.length ? t("staff.helpdesk.photos", { count: photos.length }) : t("staff.helpdesk.takePhoto")}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    capture="environment"
                    multiple
                    className="sr-only"
                    onChange={(e) => setPhotos(Array.from(e.target.files ?? []).slice(0, 3))}
                  />
                </label>
                {photos.length > 0 && (
                  <button type="button" className="mt-1 flex items-center gap-1 text-[12px] text-sand-500" onClick={() => setPhotos([])}>
                    <X className="size-3" /> {t("common.remove")}
                  </button>
                )}
              </Field>
              <Field label={t("staff.helpdesk.doctor")} hint={t("common.optional")}>
                <Input value={doctor} onChange={(e) => setDoctor(e.target.value)} />
              </Field>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title={t("staff.helpdesk.step3")} subtitle={t("staff.helpdesk.step3Hint")} />
            <CardBody>
              <TestPicker value={tests} onChange={setTests} />
            </CardBody>
          </Card>
        </div>
        <div>
          <Card className="sticky top-20">
            <CardHeader title={t("staff.helpdesk.summary")} />
            <CardBody className="space-y-4">
              <Field label={t("staff.helpdesk.feeCategory")}>
                <Select value={fee} onChange={(e) => setFee(e.target.value as typeof fee)} data-testid="fee-category">
                  {FEE_CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {t(`enums.feeCategory.${c}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              {fee !== "GENERAL" && (
                <Field label={t("staff.helpdesk.waiverReason")} hint={t("staff.helpdesk.waiverHint")} required>
                  <Textarea value={waiverReason} onChange={(e) => setWaiverReason(e.target.value)} className="min-h-16" />
                </Field>
              )}
              <Field label={t("staff.helpdesk.priority")}>
                <Select value={priority} onChange={(e) => setPriority(e.target.value as typeof priority)}>
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {t(`enums.priority.${p}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t("staff.helpdesk.smsLanguage")}>
                <Select value={smsLang} onChange={(e) => setSmsLang(e.target.value as "bn" | "en")}>
                  <option value="bn">{t("common.bangla")}</option>
                  <option value="en">{t("common.english")}</option>
                </Select>
              </Field>
              <div className="flex items-baseline justify-between border-t border-sand-100 pt-4">
                <span className="text-[13px] font-semibold uppercase tracking-wider text-sand-500">{t("common.total")}</span>
                <span className="text-2xl font-bold tabular">{formatMoney(total, lang)}</span>
              </div>
              <Button
                block
                size="lg"
                icon={<Printer className="size-4" />}
                disabled={!canCreate}
                loading={create.isPending}
                onClick={() => create.mutate()}
                data-testid="create-walkin"
              >
                {t("staff.helpdesk.create")}
              </Button>
              <p className="text-[12px] leading-relaxed text-sand-500">{t("staff.helpdesk.inlineNote")}</p>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

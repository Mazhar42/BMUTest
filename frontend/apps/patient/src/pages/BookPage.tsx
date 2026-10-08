import { unwrap, type Schemas } from "@bmu/api-client";
import { formatMoney, useI18n } from "@bmu/i18n";
import { Badge, Button, Callout, Card, cn, compressImage, Field, Input, Textarea } from "@bmu/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Camera, Check, ImagePlus, Info, Plus, Search, Trash2, X } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Screen } from "../components/Layout";
import { api, upload } from "../lib/api";
import { useErrorToast } from "../lib/errors";
import { useSession } from "../lib/session";

type Test = Schemas["TestOut"];
const STEPS = ["photos", "tests", "review"] as const;

function Steps({ step }: { step: number }) {
  const { t } = useI18n();
  return (
    <ol className="mb-5 flex gap-2 pt-2">
      {STEPS.map((s, i) => (
        <li key={s} className="flex-1">
          <div className={cn("h-1.5 rounded-full", i <= step ? "bg-brand-600" : "bg-sand-200")} />
          <div className={cn("mt-1.5 text-[12px] font-semibold", i === step ? "text-ink" : "text-sand-400")}>
            {t(`patient.book.steps.${s}`)}
          </div>
        </li>
      ))}
    </ol>
  );
}

function Photos({ files, onChange }: { files: File[]; onChange: (f: File[]) => void }) {
  const { t } = useI18n();
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);
  return (
    <div>
      <h2 className="text-[22px] font-bold">{t("patient.book.photosTitle")}</h2>
      <p className="mt-1 text-[15px] text-sand-600">{t("patient.book.photosBody")}</p>
      <div className="mt-5 grid grid-cols-3 gap-3">
        {previews.map((src, i) => (
          <div key={src} className="relative aspect-[3/4] overflow-hidden rounded-2xl bg-sand-100 ring-1 ring-sand-200">
            <img src={src} alt={t("patient.book.page", { n: i + 1 })} className="size-full object-cover" />
            <button
              type="button"
              aria-label={t("common.remove")}
              onClick={() => onChange(files.filter((_, j) => j !== i))}
              className="absolute right-1.5 top-1.5 grid size-8 place-items-center rounded-full bg-ink/70 text-white"
            >
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
        {files.length < 3 && (
          <label className="flex aspect-[3/4] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-brand-300 bg-brand-50/50 text-brand-700">
            {files.length ? <ImagePlus className="size-7" /> : <Camera className="size-7" />}
            <span className="px-2 text-center text-[13px] font-semibold">
              {files.length ? t("patient.book.addPage") : t("patient.book.takePhoto")}
            </span>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="sr-only"
              data-testid="photo-input"
              onChange={(e) => {
                const picked = Array.from(e.target.files ?? []);
                onChange([...files, ...picked].slice(0, 3));
                e.target.value = "";
              }}
            />
          </label>
        )}
      </div>
      <Callout tone="info" icon={<Info className="size-4" />} className="mt-5">
        {t("patient.book.photosTip")}
      </Callout>
    </div>
  );
}

function TestSearch({ picked, onChange }: { picked: Test[]; onChange: (t: Test[]) => void }) {
  const { t, lang } = useI18n();
  const [q, setQ] = useState("");
  const query = useDeferredValue(q.trim());
  const results = useQuery({
    queryKey: ["patient-tests", query],
    queryFn: () => unwrap(api.GET("/api/v1/patient/catalog/tests", { params: { query: { q: query || null, limit: 20 } } })),
    staleTime: 60_000,
  });
  const chosen = new Set(picked.map((x) => x.id));
  return (
    <div>
      <h2 className="text-[22px] font-bold">{t("patient.book.testsTitle")}</h2>
      <p className="mt-1 text-[15px] text-sand-600">{t("patient.book.testsBody")}</p>
      <div className="relative mt-4">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-sand-400" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("patient.book.searchPlaceholder")}
          inputSize="lg"
          className="pl-12"
          data-testid="patient-test-search"
        />
      </div>
      {picked.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {picked.map((x) => (
            <button
              key={x.id}
              type="button"
              onClick={() => onChange(picked.filter((p) => p.id !== x.id))}
              className="inline-flex items-center gap-1.5 rounded-full bg-brand-600 py-1.5 pl-3 pr-2 text-[14px] font-semibold text-white"
            >
              {x.abbreviation}
              <X className="size-4" />
            </button>
          ))}
        </div>
      )}
      <ul className="mt-3 divide-y divide-sand-100 overflow-hidden rounded-2xl bg-white ring-1 ring-sand-200">
        {(results.data ?? []).map((x) => {
          const on = chosen.has(x.id);
          return (
            <li key={x.id}>
              <button
                type="button"
                data-testid="patient-test-option"
                onClick={() => onChange(on ? picked.filter((p) => p.id !== x.id) : [...picked, x])}
                className={cn("flex w-full items-center gap-3 px-4 py-3.5 text-left", on && "bg-brand-50")}
              >
                <span
                  className={cn(
                    "grid size-7 shrink-0 place-items-center rounded-lg ring-1",
                    on ? "bg-brand-600 text-white ring-brand-600" : "text-sand-400 ring-sand-300",
                  )}
                >
                  {on ? <Check className="size-4" strokeWidth={3} /> : <Plus className="size-4" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[15.5px] font-semibold">{lang === "bn" ? x.name_bn : x.name_en}</span>
                  <span className="block text-[13px] text-sand-500">
                    {lang === "bn" ? x.name_en : x.name_bn}
                    {x.fasting_required && <Badge tone="warn" className="ml-2">{t("patient.book.fasting")}</Badge>}
                  </span>
                </span>
                <span className="text-[14px] font-semibold tabular">{formatMoney(x.price, lang)}</span>
              </button>
            </li>
          );
        })}
        {results.data?.length === 0 && <li className="px-4 py-8 text-center text-[14px] text-sand-500">{t("common.noResults")}</li>}
      </ul>
    </div>
  );
}

/** Book a test: prescription photos → tests → review → submit (ROADMAP §5.1 step 4). */
export default function BookPage() {
  const { patientId = "" } = useParams();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const onError = useErrorToast();
  const { account } = useSession();
  const patient = account?.patients.find((p) => p.id === patientId);
  const [step, setStep] = useState(0);
  const [files, setFiles] = useState<File[]>([]);
  const [tests, setTests] = useState<Test[]>([]);
  const [doctor, setDoctor] = useState("");
  const [notes, setNotes] = useState("");

  const submit = useMutation({
    mutationFn: async () => {
      let prescriptionId: string | null = null;
      if (files.length) {
        const form = new FormData();
        form.append("patient_id", patientId);
        if (doctor.trim()) form.append("doctor_name", doctor.trim());
        for (const f of files) form.append("files", await compressImage(f));
        prescriptionId = (await upload<Schemas["PrescriptionOut"]>("/api/v1/patient/prescriptions", form)).id;
      }
      return unwrap(
        api.POST("/api/v1/patient/orders", {
          body: { patient_id: patientId, prescription_id: prescriptionId, test_ids: tests.map((x) => x.id), notes: notes.trim() || null, lang },
        }),
      );
    },
    onSuccess: (order) => navigate(`/orders/${order.id}?new=1`, { replace: true }),
    onError,
  });

  const total = tests.reduce((s, x) => s + (x.price ?? 0), 0);
  const needsRx = tests.some((x) => x.requires_prescription);
  const fasting = tests.filter((x) => x.fasting_required);

  const footer =
    step === 0 ? (
      <Button block size="xl" onClick={() => setStep(1)} data-testid="book-next">
        {files.length ? t("common.continue") : t("patient.book.skipPhotos")}
      </Button>
    ) : step === 1 ? (
      <Button block size="xl" disabled={!tests.length} onClick={() => setStep(2)} data-testid="book-next">
        {t("patient.book.review")} · {formatMoney(total, lang)}
      </Button>
    ) : (
      <Button block size="xl" loading={submit.isPending} onClick={() => submit.mutate()} data-testid="book-submit">
        {t("patient.book.submit")}
      </Button>
    );

  return (
    <Screen
      back={step === 0 ? "/book" : true}
      title={patient ? patient.full_name : t("patient.home.book")}
      footer={footer}
    >
      <Steps step={step} />
      {step === 0 && <Photos files={files} onChange={setFiles} />}
      {step === 1 && <TestSearch picked={tests} onChange={setTests} />}
      {step === 2 && (
        <div className="space-y-4">
          <h2 className="text-[22px] font-bold">{t("patient.book.reviewTitle")}</h2>
          {needsRx && !files.length && (
            <Callout tone="warn">{t("patient.book.needsPrescription")}</Callout>
          )}
          <Card>
            <ul className="divide-y divide-sand-100">
              {tests.map((x) => (
                <li key={x.id} className="flex items-start gap-3 px-4 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{lang === "bn" ? x.name_bn : x.name_en}</span>
                    {(lang === "bn" ? x.prep_bn : x.prep_en) && (
                      <span className="mt-0.5 block text-[13px] text-sand-600">{lang === "bn" ? x.prep_bn : x.prep_en}</span>
                    )}
                  </span>
                  <span className="tabular">{formatMoney(x.price, lang)}</span>
                </li>
              ))}
              <li className="flex items-center justify-between bg-sand-50 px-4 py-3 font-bold">
                <span>{t("common.total")}</span>
                <span className="text-[18px] tabular">{formatMoney(total, lang)}</span>
              </li>
            </ul>
          </Card>
          {fasting.length > 0 && (
            <Callout tone="warn" title={t("patient.book.fastingTitle")}>
              {fasting.map((x) => `${x.abbreviation}: ${t("patient.book.fastingHours", { hours: x.fasting_hours ?? "?" })}`).join(" · ")}
            </Callout>
          )}
          <Callout tone="info">{t("patient.book.priceNote")}</Callout>
          {files.length > 0 && (
            <Field label={t("patient.book.doctor")} hint={t("common.optional")}>
              <Input value={doctor} onChange={(e) => setDoctor(e.target.value)} inputSize="lg" />
            </Field>
          )}
          <Field label={t("patient.book.notes")} hint={t("common.optional")}>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="min-h-20" />
          </Field>
        </div>
      )}
    </Screen>
  );
}

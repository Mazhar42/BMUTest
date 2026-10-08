import { isApiError, unwrap, type Schemas } from "@bmu/api-client";
import { maskMobile, useI18n } from "@bmu/i18n";
import { Badge, Button, Callout, Dialog, Field, Input, SegmentedControl, Select, cn } from "@bmu/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Search, UserPlus } from "lucide-react";
import { useDeferredValue, useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { useErrorToast } from "../lib/errors";

export type StaffPatient = Schemas["StaffPatientOut"];
type Duplicate = Schemas["DuplicateCandidate"];

export function patientLine(p: { age: number | null; sex: string; mobile?: string | null }, t: (k: string) => string) {
  return [p.age !== null ? `${p.age}` : "—", t(`common.sexes.${p.sex}`), p.mobile ? maskMobile(p.mobile) : null]
    .filter(Boolean)
    .join(" · ");
}

/** Search by mobile, name, hospital number or order code; pick a result or register a new patient. */
export function PatientFinder({ onPick, initialQuery = "" }: { onPick: (p: StaffPatient) => void; initialQuery?: string }) {
  const { t } = useI18n();
  const [q, setQ] = useState(initialQuery);
  const [registering, setRegistering] = useState(false);
  const query = useDeferredValue(q.trim());
  const results = useQuery({
    queryKey: ["patients", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/patients", { params: { query: { q: query } } })),
    enabled: query.length >= 2,
  });

  return (
    <div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-sand-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("staff.patients.searchPlaceholder")}
            className="pl-10"
            inputSize="lg"
            autoFocus
            data-testid="patient-search"
          />
        </div>
        <Button variant="secondary" size="lg" icon={<UserPlus className="size-4" />} onClick={() => setRegistering(true)}>
          {t("staff.patients.register")}
        </Button>
      </div>
      {query.length >= 2 && (
        <ul className="mt-3 divide-y divide-sand-100 overflow-hidden rounded-xl border border-sand-200 bg-white">
          {(results.data ?? []).map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onPick(p)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-brand-50/50"
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-50 text-[13px] font-bold text-brand-700">
                  {p.full_name.slice(0, 1)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14.5px] font-semibold">
                    {p.full_name}
                    {p.full_name_bn && <span className="ml-2 font-normal text-sand-500">{p.full_name_bn}</span>}
                  </span>
                  <span className="block text-[12.5px] text-sand-500">{patientLine(p, t)}</span>
                </span>
                {p.hospital_patient_no && <Badge>{p.hospital_patient_no}</Badge>}
                <Badge tone="neutral">{t(`enums.channel.${p.created_channel}`)}</Badge>
              </button>
            </li>
          ))}
          {results.data?.length === 0 && (
            <li className="px-4 py-6 text-center text-[13px] text-sand-500">{t("staff.patients.noMatch")}</li>
          )}
        </ul>
      )}
      <RegisterPatientDialog
        open={registering}
        onOpenChange={setRegistering}
        onRegistered={(p) => {
          setRegistering(false);
          onPick(p);
        }}
        onUseExisting={(id) => {
          setRegistering(false);
          void unwrap(api.GET("/api/v1/staff/patients/{patient_id}", { params: { path: { patient_id: id } } })).then(onPick);
        }}
      />
    </div>
  );
}

export function RegisterPatientDialog({
  open,
  onOpenChange,
  onRegistered,
  onUseExisting,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onRegistered: (p: StaffPatient) => void;
  onUseExisting: (id: string) => void;
}) {
  const { t } = useI18n();
  const onError = useErrorToast();
  const [form, setForm] = useState({
    full_name: "",
    full_name_bn: "",
    sex: "F",
    ageMode: "age" as "age" | "dob",
    age_years: "",
    date_of_birth: "",
    mobile: "",
    hospital_patient_no: "",
  });
  const [duplicates, setDuplicates] = useState<Duplicate[] | null>(null);

  const register = useMutation({
    mutationFn: (force: boolean) =>
      unwrap(
        api.POST("/api/v1/staff/patients", {
          body: {
            full_name: form.full_name.trim(),
            full_name_bn: form.full_name_bn.trim() || null,
            sex: form.sex as "M" | "F" | "O",
            age_years: form.ageMode === "age" ? Number(form.age_years) : null,
            date_of_birth: form.ageMode === "dob" ? form.date_of_birth : null,
            mobile: form.mobile.trim() || null,
            hospital_patient_no: form.hospital_patient_no.trim() || null,
            relation_to_account: "SELF",
            force,
          },
        }),
      ),
    onSuccess: (p) => {
      setDuplicates(null);
      onRegistered(p);
    },
    onError: (e) => {
      if (isApiError(e) && e.code === "POSSIBLE_DUPLICATE") {
        setDuplicates((e.params.candidates as Duplicate[] | undefined) ?? []);
        return;
      }
      onError(e);
    },
  });

  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  const valid =
    form.full_name.trim().length >= 2 && (form.ageMode === "age" ? form.age_years !== "" : form.date_of_birth !== "");

  function submit(e: FormEvent) {
    e.preventDefault();
    register.mutate(false);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setDuplicates(null);
        onOpenChange(v);
      }}
      title={t("staff.patients.registerTitle")}
      description={t("staff.patients.registerHint")}
      size="lg"
      footer={
        duplicates ? (
          <>
            <Button variant="ghost" onClick={() => setDuplicates(null)}>
              {t("common.back")}
            </Button>
            <Button variant="danger" loading={register.isPending} onClick={() => register.mutate(true)}>
              {t("staff.patients.registerAnyway")}
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" form="register-patient" loading={register.isPending} disabled={!valid}>
              {t("staff.patients.register")}
            </Button>
          </>
        )
      }
    >
      {duplicates ? (
        <div>
          <Callout tone="warn" icon={<AlertTriangle className="size-4" />} title={t("errors.possible_duplicate")}>
            {t("staff.patients.duplicateHint")}
          </Callout>
          <ul className="mt-3 space-y-2">
            {duplicates.map((d) => (
              <li key={d.id} className="flex items-center gap-3 rounded-xl border border-sand-200 px-4 py-3">
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{d.full_name}</span>
                  <span className="block text-[12.5px] text-sand-500">
                    {patientLine(d, t)} · {t(`staff.patients.dupReason.${d.reason}`)}
                  </span>
                </span>
                <Button size="sm" variant="secondary" onClick={() => onUseExisting(d.id)}>
                  {t("staff.patients.useThis")}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <form id="register-patient" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label={t("staff.patients.fullName")} required>
            <Input value={form.full_name} onChange={(e) => set("full_name")(e.target.value)} autoFocus data-testid="reg-name" />
          </Field>
          <Field label={t("staff.patients.fullNameBn")}>
            <Input value={form.full_name_bn} onChange={(e) => set("full_name_bn")(e.target.value)} lang="bn" />
          </Field>
          <Field label={t("common.sex")} required>
            <Select value={form.sex} onChange={(e) => set("sex")(e.target.value)}>
              {["F", "M", "O"].map((s) => (
                <option key={s} value={s}>
                  {t(`common.sexes.${s}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("common.mobile")} hint={t("staff.patients.mobileHint")}>
            <Input
              value={form.mobile}
              onChange={(e) => set("mobile")(e.target.value)}
              inputMode="tel"
              placeholder="01XXXXXXXXX"
              data-testid="reg-mobile"
            />
          </Field>
          <div className="sm:col-span-2">
            <SegmentedControl
              size="sm"
              value={form.ageMode}
              onChange={(v) => setForm((f) => ({ ...f, ageMode: v }))}
              options={[
                { value: "age", label: t("staff.patients.ageYears") },
                { value: "dob", label: t("staff.patients.dob") },
              ]}
            />
            <div className={cn("mt-2 max-w-xs")}>
              {form.ageMode === "age" ? (
                <Input
                  type="number"
                  min={0}
                  max={130}
                  value={form.age_years}
                  onChange={(e) => set("age_years")(e.target.value)}
                  data-testid="reg-age"
                />
              ) : (
                <Input type="date" value={form.date_of_birth} onChange={(e) => set("date_of_birth")(e.target.value)} />
              )}
            </div>
          </div>
          <Field label={t("staff.patients.hospitalNo")} hint={t("common.optional")}>
            <Input value={form.hospital_patient_no} onChange={(e) => set("hospital_patient_no")(e.target.value)} />
          </Field>
        </form>
      )}
    </Dialog>
  );
}

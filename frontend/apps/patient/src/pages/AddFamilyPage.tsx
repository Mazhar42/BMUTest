import { unwrap } from "@bmu/api-client";
import { useI18n } from "@bmu/i18n";
import { Button, Field, Input, SegmentedControl, Select } from "@bmu/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Screen } from "../components/Layout";
import { api } from "../lib/api";
import { useErrorToast } from "../lib/errors";

const RELATIONS = ["SPOUSE", "CHILD", "PARENT", "SIBLING", "OTHER"] as const;
type Relation = "SELF" | (typeof RELATIONS)[number];

/** Add myself or a family member: name, sex, date of birth or age, relation (ROADMAP M2). */
export default function AddFamilyPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [params] = useSearchParams();
  const isSelf = params.get("self") === "1";
  const [f, setF] = useState({
    full_name: "",
    full_name_bn: "",
    sex: "F" as "M" | "F" | "O",
    mode: "age" as "age" | "dob",
    age: "",
    dob: "",
    relation: (isSelf ? "SELF" : "CHILD") as Relation,
  });

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/patient/patients", {
          body: {
            full_name: f.full_name.trim(),
            full_name_bn: f.full_name_bn.trim() || null,
            sex: f.sex,
            age_years: f.mode === "age" ? Number(f.age) : null,
            date_of_birth: f.mode === "dob" ? f.dob : null,
            relation_to_account: f.relation,
          },
        }),
      ),
    onSuccess: async (p) => {
      await qc.invalidateQueries({ queryKey: ["me"] });
      navigate(`/book/${p.id}`, { replace: true });
    },
    onError,
  });

  const valid = f.full_name.trim().length >= 2 && (f.mode === "age" ? f.age !== "" && Number(f.age) <= 130 : !!f.dob);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (valid) save.mutate();
  }

  return (
    <Screen
      back="/book"
      title={isSelf ? t("patient.family.selfTitle") : t("patient.family.title")}
      footer={
        <Button block size="xl" type="submit" form="family" loading={save.isPending} disabled={!valid} data-testid="family-save">
          {t("common.save")}
        </Button>
      }
    >
      <form id="family" onSubmit={submit} className="space-y-5 pt-4">
        <Field label={t("patient.family.name")} hint={t("patient.family.nameHint")} required>
          <Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} inputSize="lg" autoFocus data-testid="family-name" />
        </Field>
        <Field label={t("patient.family.nameBn")} hint={t("common.optional")}>
          <Input value={f.full_name_bn} onChange={(e) => setF({ ...f, full_name_bn: e.target.value })} inputSize="lg" lang="bn" />
        </Field>
        <Field label={t("common.sex")}>
          <SegmentedControl
            className="w-full [&>button]:flex-1"
            value={f.sex}
            onChange={(v) => setF({ ...f, sex: v })}
            options={(["F", "M", "O"] as const).map((s) => ({ value: s, label: t(`common.sexes.${s}`) }))}
          />
        </Field>
        <Field label={t("patient.family.age")}>
          <SegmentedControl
            size="sm"
            value={f.mode}
            onChange={(v) => setF({ ...f, mode: v })}
            options={[
              { value: "age", label: t("patient.family.ageYears") },
              { value: "dob", label: t("patient.family.dob") },
            ]}
          />
          <div className="mt-2">
            {f.mode === "age" ? (
              <Input
                type="number"
                inputMode="numeric"
                min={0}
                max={130}
                value={f.age}
                onChange={(e) => setF({ ...f, age: e.target.value })}
                inputSize="lg"
                data-testid="family-age"
              />
            ) : (
              <Input type="date" value={f.dob} onChange={(e) => setF({ ...f, dob: e.target.value })} inputSize="lg" />
            )}
          </div>
        </Field>
        {!isSelf && (
          <Field label={t("patient.family.relation")}>
            <Select value={f.relation} onChange={(e) => setF({ ...f, relation: e.target.value as Relation })} className="h-12 text-base">
              {RELATIONS.map((r) => (
                <option key={r} value={r}>
                  {t(`enums.relation.${r}`)}
                </option>
              ))}
            </Select>
          </Field>
        )}
      </form>
    </Screen>
  );
}

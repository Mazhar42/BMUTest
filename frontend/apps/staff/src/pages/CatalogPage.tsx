import { unwrap, type Schemas } from "@bmu/api-client";
import { formatDateTime, formatMoney, useI18n } from "@bmu/i18n";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardBody,
  Checkbox,
  Dialog,
  Field,
  Input,
  PageHeader,
  Select,
  Switch,
  Table,
  Tabs,
  TD,
  Textarea,
  TH,
  toast,
  TR,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Info, Pencil, Plus, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { api, upload } from "../lib/api";
import { useErrorToast } from "../lib/errors";

type Test = Schemas["TestOut"];
type Department = Schemas["DepartmentOut"];

const SPECIMENS = ["BLOOD", "URINE", "STOOL", "SWAB", "OTHER"] as const;
const CONTAINERS = [
  "EDTA",
  "PLAIN",
  "SST",
  "FLUORIDE",
  "CITRATE",
  "HEPARIN",
  "URINE_CUP",
  "STOOL_CUP",
  "BLOOD_CULTURE",
  "SWAB_TUBE",
  "OTHER",
] as const;
const RESOURCES = ["BLOOD_COLLECTION", "URINE", "SPECIAL"] as const;

export default function CatalogPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState("tests");
  return (
    <div>
      <PageHeader eyebrow={t("nav.groups.admin")} title={t("nav.items.catalog")} subtitle={t("staff.catalog.subtitle")} />
      <Callout tone="warn" icon={<Info className="size-4" />} className="mb-5">
        {t("common.placeholderData")}
      </Callout>
      <Tabs
        value={tab}
        onValueChange={setTab}
        tabs={[
          { value: "tests", label: t("staff.catalog.tests"), content: <TestsTab /> },
          { value: "departments", label: t("staff.catalog.departments"), content: <DepartmentsTab /> },
          { value: "import", label: t("staff.catalog.import"), content: <ImportTab /> },
        ]}
      />
    </div>
  );
}

function useDepartments() {
  return useQuery({
    queryKey: ["departments"],
    queryFn: () => unwrap(api.GET("/api/v1/staff/catalog/departments")),
    staleTime: 60_000,
  });
}

function TestsTab() {
  const { t, lang } = useI18n();
  const [q, setQ] = useState("");
  const [inactive, setInactive] = useState(false);
  const [editing, setEditing] = useState<Test | "new" | null>(null);
  const query = useDeferredValue(q.trim());
  const tests = useQuery({
    queryKey: ["catalog-admin", query, inactive],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/staff/catalog/tests", {
          params: { query: { q: query || null, include_inactive: inactive, limit: 500 } },
        }),
      ),
  });
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-sand-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("staff.tests.searchPlaceholder")} className="pl-10" />
        </div>
        <Checkbox label={t("staff.catalog.showInactive")} checked={inactive} onChange={(e) => setInactive(e.target.checked)} />
        <Button icon={<Plus className="size-4" />} onClick={() => setEditing("new")}>
          {t("staff.catalog.newTest")}
        </Button>
      </div>
      <Card>
        <Table>
          <thead>
            <tr>
              <TH>{t("common.code")}</TH>
              <TH>{t("common.name")}</TH>
              <TH>{t("staff.catalog.department")}</TH>
              <TH>{t("staff.orderDetail.container")}</TH>
              <TH>{t("staff.catalog.fasting")}</TH>
              <TH>{t("staff.catalog.tat")}</TH>
              <TH className="text-right">{t("staff.catalog.price")}</TH>
              <TH />
            </tr>
          </thead>
          <tbody>
            {(tests.data ?? []).map((x) => (
              <TR key={x.id} className={x.active ? "" : "opacity-50"}>
                <TD className="font-mono text-[13px] font-semibold">{x.code}</TD>
                <TD>
                  <div className="font-semibold">{x.name_en}</div>
                  <div className="text-[12.5px] text-sand-500">{x.name_bn}</div>
                </TD>
                <TD className="text-[13px]">{lang === "bn" ? x.department.name_bn : x.department.name_en}</TD>
                <TD className="text-[13px]">{t(`enums.container.${x.container_type}`)}</TD>
                <TD>{x.fasting_required ? <Badge tone="warn">{x.fasting_hours ?? "?"} h</Badge> : "—"}</TD>
                <TD className="tabular text-[13px]">{x.tat_hours} h</TD>
                <TD className="text-right tabular">{formatMoney(x.price, lang)}</TD>
                <TD className="text-right">
                  <Button size="sm" variant="ghost" icon={<Pencil className="size-3.5" />} onClick={() => setEditing(x)}>
                    {t("common.edit")}
                  </Button>
                </TD>
              </TR>
            ))}
          </tbody>
        </Table>
      </Card>
      {editing && <TestDialog test={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function TestDialog({ test, onClose }: { test: Test | null; onClose: () => void }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const depts = useDepartments();
  const detail = useQuery({
    queryKey: ["catalog-test", test?.id],
    queryFn: () => unwrap(api.GET("/api/v1/staff/catalog/tests/{test_id}", { params: { path: { test_id: test!.id } } })),
    enabled: !!test,
  });
  const [f, setF] = useState(() => ({
    code: test?.code ?? "",
    name_en: test?.name_en ?? "",
    name_bn: test?.name_bn ?? "",
    abbreviation: test?.abbreviation ?? "",
    aliases: (test?.aliases ?? []).join(" | "),
    department_id: test?.department.id ?? "",
    specimen_type: test?.specimen_type ?? "BLOOD",
    container_type: test?.container_type ?? "EDTA",
    collection_resource: test?.collection_resource ?? "BLOOD_COLLECTION",
    fasting_required: test?.fasting_required ?? false,
    fasting_hours: test?.fasting_hours?.toString() ?? "",
    prep_en: test?.prep_en ?? "",
    prep_bn: test?.prep_bn ?? "",
    tat_hours: String(test?.tat_hours ?? 24),
    requires_prescription: test?.requires_prescription ?? true,
    active: test?.active ?? true,
    price: test?.price != null ? String(test.price / 100) : "",
  }));
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const save = useMutation({
    mutationFn: async () => {
      const common = {
        name_en: f.name_en.trim(),
        name_bn: f.name_bn.trim(),
        abbreviation: f.abbreviation.trim(),
        aliases: f.aliases.split("|").map((a) => a.trim()).filter(Boolean),
        department_id: f.department_id,
        specimen_type: f.specimen_type,
        container_type: f.container_type,
        collection_resource: f.collection_resource,
        fasting_required: f.fasting_required,
        fasting_hours: f.fasting_hours ? Number(f.fasting_hours) : null,
        prep_en: f.prep_en.trim() || null,
        prep_bn: f.prep_bn.trim() || null,
        tat_hours: Number(f.tat_hours),
        requires_prescription: f.requires_prescription,
        active: f.active,
      };
      const price = f.price === "" ? null : Math.round(Number(f.price) * 100);
      if (!test) {
        return unwrap(api.POST("/api/v1/staff/catalog/tests", { body: { ...common, code: f.code.trim().toUpperCase(), price, home_collectable: true, sort: 0 } }));
      }
      const updated = await unwrap(
        api.PATCH("/api/v1/staff/catalog/tests/{test_id}", { params: { path: { test_id: test.id } }, body: common }),
      );
      if (price !== null && price !== test.price) {
        return unwrap(
          api.POST("/api/v1/staff/catalog/tests/{test_id}/prices", {
            params: { path: { test_id: test.id } },
            body: { amount: price, fee_category: "GENERAL" },
          }),
        );
      }
      return updated;
    },
    onSuccess: () => {
      toast.success(t("common.save"));
      void qc.invalidateQueries({ queryKey: ["catalog-admin"] });
      void qc.invalidateQueries({ queryKey: ["catalog-tests"] });
      onClose();
    },
    onError,
  });

  return (
    <Dialog
      open
      onOpenChange={(v) => !v && onClose()}
      size="xl"
      title={test ? `${test.code} · ${test.name_en}` : t("staff.catalog.newTest")}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button loading={save.isPending} onClick={() => save.mutate()} disabled={!f.name_en || !f.department_id}>
            {t("common.save")}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 md:grid-cols-3">
        {!test && (
          <Field label={t("common.code")} required>
            <Input value={f.code} onChange={(e) => set("code", e.target.value)} />
          </Field>
        )}
        <Field label={t("staff.catalog.nameEn")} required>
          <Input value={f.name_en} onChange={(e) => set("name_en", e.target.value)} />
        </Field>
        <Field label={t("staff.catalog.nameBn")} required>
          <Input value={f.name_bn} onChange={(e) => set("name_bn", e.target.value)} lang="bn" />
        </Field>
        <Field label={t("staff.catalog.abbreviation")} required>
          <Input value={f.abbreviation} onChange={(e) => set("abbreviation", e.target.value)} />
        </Field>
        <Field label={t("staff.catalog.aliases")} hint={t("staff.catalog.aliasesHint")} className="md:col-span-2">
          <Input value={f.aliases} onChange={(e) => set("aliases", e.target.value)} />
        </Field>
        <Field label={t("staff.catalog.department")} required>
          <Select value={f.department_id} onChange={(e) => set("department_id", e.target.value)}>
            <option value="">—</option>
            {(depts.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {lang === "bn" ? d.name_bn : d.name_en}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("staff.catalog.specimen")}>
          <Select value={f.specimen_type} onChange={(e) => set("specimen_type", e.target.value as typeof f.specimen_type)}>
            {SPECIMENS.map((s) => (
              <option key={s} value={s}>
                {t(`enums.specimen.${s}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("staff.orderDetail.container")}>
          <Select value={f.container_type} onChange={(e) => set("container_type", e.target.value as typeof f.container_type)}>
            {CONTAINERS.map((c) => (
              <option key={c} value={c}>
                {t(`enums.container.${c}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("staff.catalog.resource")}>
          <Select
            value={f.collection_resource}
            onChange={(e) => set("collection_resource", e.target.value as typeof f.collection_resource)}
          >
            {RESOURCES.map((r) => (
              <option key={r} value={r}>
                {t(`enums.resource.${r}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("staff.catalog.tat")}>
          <Input type="number" min={1} value={f.tat_hours} onChange={(e) => set("tat_hours", e.target.value)} />
        </Field>
        <Field label={t("staff.catalog.priceTaka")} hint={t("staff.catalog.priceHint")}>
          <Input type="number" min={0} step="0.01" value={f.price} onChange={(e) => set("price", e.target.value)} />
        </Field>
        <Field label={t("staff.catalog.fastingHours")}>
          <Input
            type="number"
            min={0}
            value={f.fasting_hours}
            disabled={!f.fasting_required}
            onChange={(e) => set("fasting_hours", e.target.value)}
          />
        </Field>
        <Field label={t("staff.catalog.prepEn")} className="md:col-span-3">
          <Textarea value={f.prep_en} onChange={(e) => set("prep_en", e.target.value)} className="min-h-16" />
        </Field>
        <Field label={t("staff.catalog.prepBn")} className="md:col-span-3">
          <Textarea value={f.prep_bn} onChange={(e) => set("prep_bn", e.target.value)} className="min-h-16" lang="bn" />
        </Field>
        <div className="space-y-3 md:col-span-3">
          <Switch checked={f.fasting_required} onCheckedChange={(v) => set("fasting_required", v)} label={t("staff.catalog.fasting")} />
          <Switch
            checked={f.requires_prescription}
            onCheckedChange={(v) => set("requires_prescription", v)}
            label={t("staff.catalog.requiresPrescription")}
          />
          <Switch checked={f.active} onCheckedChange={(v) => set("active", v)} label={t("staff.catalog.active")} />
        </div>
      </div>
      {detail.data && detail.data.prices.length > 0 && (
        <div className="mt-6">
          <h4 className="mb-2 text-[13px] font-semibold uppercase tracking-wider text-sand-500">{t("staff.catalog.priceHistory")}</h4>
          <ul className="divide-y divide-sand-100 rounded-xl border border-sand-200 text-[13.5px]">
            {detail.data.prices.map((p) => (
              <li key={p.id} className="flex justify-between px-4 py-2">
                <span>
                  {formatDateTime(p.effective_from, lang)} → {p.effective_to ? formatDateTime(p.effective_to, lang) : t("staff.catalog.current")}
                </span>
                <span className="font-semibold tabular">{formatMoney(p.amount, lang)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Dialog>
  );
}

function DepartmentsTab() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const depts = useDepartments();
  const [editing, setEditing] = useState<Department | "new" | null>(null);
  const [f, setF] = useState({ code: "", name_en: "", name_bn: "", result_mode: "STRUCTURED", sort: "0", active: true });

  function open(d: Department | "new") {
    setEditing(d);
    setF(
      d === "new"
        ? { code: "", name_en: "", name_bn: "", result_mode: "STRUCTURED", sort: "0", active: true }
        : { code: d.code, name_en: d.name_en, name_bn: d.name_bn, result_mode: d.result_mode, sort: String(d.sort), active: d.active },
    );
  }

  const save = useMutation({
    mutationFn: () => {
      const body = {
        code: f.code.trim().toUpperCase(),
        name_en: f.name_en.trim(),
        name_bn: f.name_bn.trim(),
        result_mode: f.result_mode as "STRUCTURED" | "PDF_UPLOAD",
        sort: Number(f.sort),
        active: f.active,
        report_signatory_staff_ids: editing && editing !== "new" ? editing.report_signatory_staff_ids : [],
      };
      return editing && editing !== "new"
        ? unwrap(api.PUT("/api/v1/staff/catalog/departments/{dept_id}", { params: { path: { dept_id: editing.id } }, body }))
        : unwrap(api.POST("/api/v1/staff/catalog/departments", { body }));
    },
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["departments"] });
    },
    onError,
  });

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button icon={<Plus className="size-4" />} onClick={() => open("new")}>
          {t("staff.catalog.newDepartment")}
        </Button>
      </div>
      <Card>
        <Table>
          <thead>
            <tr>
              <TH>{t("common.code")}</TH>
              <TH>{t("common.name")}</TH>
              <TH>{t("staff.catalog.resultMode")}</TH>
              <TH>{t("common.status")}</TH>
              <TH />
            </tr>
          </thead>
          <tbody>
            {(depts.data ?? []).map((d) => (
              <TR key={d.id}>
                <TD className="font-mono text-[13px] font-semibold">{d.code}</TD>
                <TD>
                  <div className="font-semibold">{d.name_en}</div>
                  <div className="text-[12.5px] text-sand-500">{d.name_bn}</div>
                </TD>
                <TD>
                  <Badge tone={d.result_mode === "PDF_UPLOAD" ? "info" : "brand"}>{t(`enums.resultMode.${d.result_mode}`)}</Badge>
                </TD>
                <TD>{d.active ? <Badge tone="ok">{t("staff.catalog.active")}</Badge> : <Badge>{t("staff.catalog.inactive")}</Badge>}</TD>
                <TD className="text-right">
                  <Button size="sm" variant="ghost" icon={<Pencil className="size-3.5" />} onClick={() => open(d)}>
                    {t("common.edit")}
                  </Button>
                </TD>
              </TR>
            ))}
          </tbody>
        </Table>
      </Card>
      <Dialog
        open={editing !== null}
        onOpenChange={(v) => !v && setEditing(null)}
        title={editing === "new" ? t("staff.catalog.newDepartment") : t("staff.catalog.departments")}
        footer={
          <Button loading={save.isPending} onClick={() => save.mutate()} disabled={!f.code || !f.name_en || !f.name_bn}>
            {t("common.save")}
          </Button>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("common.code")}>
            <Input value={f.code} disabled={editing !== "new"} onChange={(e) => setF({ ...f, code: e.target.value })} />
          </Field>
          <Field label={t("staff.catalog.resultMode")}>
            <Select value={f.result_mode} onChange={(e) => setF({ ...f, result_mode: e.target.value })}>
              <option value="STRUCTURED">{t("enums.resultMode.STRUCTURED")}</option>
              <option value="PDF_UPLOAD">{t("enums.resultMode.PDF_UPLOAD")}</option>
            </Select>
          </Field>
          <Field label={t("staff.catalog.nameEn")}>
            <Input value={f.name_en} onChange={(e) => setF({ ...f, name_en: e.target.value })} />
          </Field>
          <Field label={t("staff.catalog.nameBn")}>
            <Input value={f.name_bn} onChange={(e) => setF({ ...f, name_bn: e.target.value })} lang="bn" />
          </Field>
          <Switch checked={f.active} onCheckedChange={(v) => setF({ ...f, active: v })} label={t("staff.catalog.active")} />
        </div>
      </Dialog>
    </div>
  );
}

function ImportTab() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [results, setResults] = useState<Schemas["ImportResult"][]>([]);
  const run = useMutation({
    mutationFn: ({ kind, file }: { kind: string; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      return upload<Schemas["ImportResult"]>(`/api/v1/staff/catalog/import/${kind}`, form);
    },
    onSuccess: (r) => {
      setResults((prev) => [r, ...prev]);
      void qc.invalidateQueries();
    },
    onError,
  });
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
      <Card>
        <CardBody className="space-y-4">
          <p className="text-[14px] text-sand-600">{t("staff.catalog.importHint")}</p>
          {(["departments", "tests", "parameters"] as const).map((kind) => (
            <label
              key={kind}
              className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-sand-300 px-4 py-3 hover:border-brand-400"
            >
              <FileUp className="size-5 text-brand-600" />
              <span className="flex-1">
                <span className="block font-semibold">{kind}.csv</span>
                <span className="block text-[12.5px] text-sand-500">{t(`staff.catalog.importKinds.${kind}`)}</span>
              </span>
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) run.mutate({ kind, file });
                  e.target.value = "";
                }}
              />
            </label>
          ))}
        </CardBody>
      </Card>
      <div className="space-y-3">
        {results.map((r, i) => (
          <Card key={i} className="p-4">
            <div className="font-semibold">{r.kind}</div>
            <div className="mt-1 text-[13.5px] text-sand-600">
              {t("staff.catalog.importResult", {
                created: r.created,
                updated: r.updated,
                unchanged: r.unchanged,
                prices: r.price_changes,
              })}
            </div>
            {r.errors.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-[13px] text-danger-700">
                {r.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

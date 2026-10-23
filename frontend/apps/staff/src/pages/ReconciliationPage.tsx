import { unwrap, type Schemas } from "@bmu/api-client";
import { formatDate, formatMoney, formatRelative, useI18n } from "@bmu/i18n";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Dialog,
  EmptyState,
  Field,
  Input,
  OrderCode,
  PageHeader,
  Table,
  TD,
  Textarea,
  TH,
  toast,
  TR,
  type Tone,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Receipt } from "lucide-react";
import { useState } from "react";

import { api, upload } from "../lib/api";
import { useErrorToast } from "../lib/errors";

type Line = Schemas["LineOut"];
const TONE: Record<string, Tone> = { UNMATCHED: "warn", AMOUNT_MISMATCH: "danger", DUPLICATE: "violet", MATCHED: "ok", RESOLVED: "neutral" };

/** Bank statement CSV → auto-match to teller payments by order code and amount → exceptions screen. */
export default function ReconciliationPage() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [file, setFile] = useState<File | null>(null);
  const [m, setM] = useState({
    bank_name: "",
    date_column: "Date",
    amount_column: "Credit",
    reference_column: "Narration",
    receipt_column: "",
    date_format: "%d/%m/%Y",
  });
  const [resolving, setResolving] = useState<Line | null>(null);
  const [note, setNote] = useState("");
  const [last, setLast] = useState<Schemas["ImportOut"] | null>(null);

  const mappings = useQuery({ queryKey: ["bank-mappings"], queryFn: () => unwrap(api.GET("/api/v1/staff/reconciliation/mappings")) });
  const imports = useQuery({ queryKey: ["bank-imports"], queryFn: () => unwrap(api.GET("/api/v1/staff/reconciliation/imports")) });
  const exceptions = useQuery({ queryKey: ["bank-exceptions"], queryFn: () => unwrap(api.GET("/api/v1/staff/reconciliation/exceptions")) });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["bank-imports"] });
    void qc.invalidateQueries({ queryKey: ["bank-exceptions"] });
    void qc.invalidateQueries({ queryKey: ["bank-mappings"] });
  };

  const send = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("file", file!);
      for (const [k, v] of Object.entries(m)) if (v) form.append(k, v);
      return upload<Schemas["ImportOut"]>("/api/v1/staff/reconciliation/import", form);
    },
    onSuccess: (out) => {
      setLast(out);
      setFile(null);
      refresh();
    },
    onError,
  });
  const resolve = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/staff/reconciliation/lines/{line_id}/resolve", { params: { path: { line_id: resolving!.id } }, body: { note: note.trim() } })),
    onSuccess: () => {
      toast.success(t("staff.recon.resolved"));
      setResolving(null);
      setNote("");
      refresh();
    },
    onError,
  });

  function applyMapping(bank: string) {
    const found = mappings.data?.find((x) => x.bank_name === bank);
    if (found) setM({ ...found, receipt_column: found.receipt_column ?? "" });
  }

  const lines = exceptions.data ?? [];
  return (
    <div>
      <PageHeader eyebrow={t("nav.groups.payments")} title={t("nav.items.reconciliation")} subtitle={t("staff.recon.subtitle")} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <CardHeader icon={<FileUp className="size-4" />} title={t("staff.recon.upload")} subtitle={t("staff.recon.uploadHint")} />
          <CardBody className="space-y-4">
            {(mappings.data?.length ?? 0) > 0 && (
              <div className="flex flex-wrap gap-2">
                {mappings.data!.map((x) => (
                  <Button key={x.bank_name} size="sm" variant="secondary" onClick={() => applyMapping(x.bank_name)}>
                    {x.bank_name}
                  </Button>
                ))}
              </div>
            )}
            <Field label={t("staff.recon.bank")} required>
              <Input value={m.bank_name} onChange={(e) => setM({ ...m, bank_name: e.target.value })} data-testid="recon-bank" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("staff.recon.colDate")}>
                <Input value={m.date_column} onChange={(e) => setM({ ...m, date_column: e.target.value })} />
              </Field>
              <Field label={t("staff.recon.colAmount")} hint={t("staff.recon.colAmountHint")}>
                <Input value={m.amount_column} onChange={(e) => setM({ ...m, amount_column: e.target.value })} />
              </Field>
              <Field label={t("staff.recon.colReference")} hint={t("staff.recon.colReferenceHint")}>
                <Input value={m.reference_column} onChange={(e) => setM({ ...m, reference_column: e.target.value })} />
              </Field>
              <Field label={t("staff.recon.colReceipt")} hint={t("common.optional")}>
                <Input value={m.receipt_column} onChange={(e) => setM({ ...m, receipt_column: e.target.value })} />
              </Field>
              <Field label={t("staff.recon.dateFormat")} hint="%d/%m/%Y">
                <Input value={m.date_format} onChange={(e) => setM({ ...m, date_format: e.target.value })} className="font-mono" />
              </Field>
            </div>
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-sand-300 px-4 py-3 hover:border-brand-400">
              <FileUp className="size-5 text-brand-600" />
              <span className="min-w-0 flex-1 truncate text-[14px]">{file ? file.name : t("staff.recon.chooseFile")}</span>
              <input type="file" accept=".csv,text/csv" className="sr-only" data-testid="recon-file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <Button block loading={send.isPending} disabled={!file || !m.bank_name.trim()} onClick={() => send.mutate()} data-testid="recon-upload">
              {t("staff.recon.import")}
            </Button>
            {last && (
              <p className="rounded-xl bg-brand-50 p-3 text-[13.5px] text-brand-800" data-testid="recon-summary">
                {t("staff.recon.summary", { rows: last.rows, matched: last.matched, exceptions: last.exceptions, skipped: last.skipped })}
              </p>
            )}
            {(imports.data?.length ?? 0) > 0 && (
              <ul className="divide-y divide-sand-100 text-[13px]">
                {imports.data!.slice(0, 5).map((i) => (
                  <li key={i.id} className="flex justify-between py-1.5">
                    <span className="truncate">{i.bank_name} · {i.filename}</span>
                    <span className="text-sand-500">{i.matched}/{i.rows} · {formatRelative(i.created_at, lang)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader icon={<Receipt className="size-4" />} title={t("staff.recon.exceptions")} subtitle={t("staff.recon.exceptionsHint")} />
          {lines.length === 0 && !exceptions.isLoading ? (
            <EmptyState title={t("staff.recon.none")} />
          ) : (
            <Table>
              <thead>
                <tr>
                  <TH>{t("common.date")}</TH>
                  <TH>{t("staff.recon.reference")}</TH>
                  <TH className="text-right">{t("common.amount")}</TH>
                  <TH>{t("common.status")}</TH>
                  <TH />
                </tr>
              </thead>
              <tbody>
                {lines.map((l) => (
                  <TR key={l.id} data-testid="exception-row">
                    <TD className="text-[13px]">{l.txn_date ? formatDate(l.txn_date, lang, "short") : "—"}</TD>
                    <TD className="max-w-[16rem] text-[13px]">
                      <div className="truncate">{l.reference}</div>
                      {l.order_code && <OrderCode code={l.order_code} size="sm" />}
                      {l.note && <div className="text-sand-500">{l.note}</div>}
                    </TD>
                    <TD className="text-right tabular">{formatMoney(l.amount, lang)}</TD>
                    <TD>
                      <Badge tone={TONE[l.match] ?? "neutral"}>{t(`enums.lineMatch.${l.match}`)}</Badge>
                    </TD>
                    <TD className="text-right">
                      <Button size="sm" variant="outline" onClick={() => { setNote(""); setResolving(l); }}>
                        {t("staff.recon.resolve")}
                      </Button>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>
      <Dialog
        open={!!resolving}
        onOpenChange={(v) => !v && setResolving(null)}
        title={t("staff.recon.resolve")}
        description={resolving ? `${formatMoney(resolving.amount, lang)} · ${resolving.reference.slice(0, 60)}` : undefined}
        footer={
          <Button loading={resolve.isPending} disabled={note.trim().length < 3} onClick={() => resolve.mutate()}>
            {t("common.confirm")}
          </Button>
        }
      >
        <Field label={t("common.notes")} hint={t("staff.recon.resolveHint")}>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
        </Field>
      </Dialog>
    </div>
  );
}

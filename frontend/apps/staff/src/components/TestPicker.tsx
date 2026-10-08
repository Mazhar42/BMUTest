import { unwrap, type Schemas } from "@bmu/api-client";
import { formatMoney, useI18n } from "@bmu/i18n";
import { Badge, cn, Input } from "@bmu/ui";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, X } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { api } from "../lib/api";

export type PickedTest = Pick<Schemas["TestOut"], "id" | "code" | "name_en" | "name_bn" | "abbreviation" | "price"> & {
  fasting_required?: boolean;
};

/** Search the catalog (aliases, Bangla or English) and build the list of tests for an order. */
export function TestPicker({
  value,
  onChange,
  autoFocus,
}: {
  value: PickedTest[];
  onChange: (tests: PickedTest[]) => void;
  autoFocus?: boolean;
}) {
  const { t, lang } = useI18n();
  const [q, setQ] = useState("");
  const query = useDeferredValue(q.trim());
  const results = useQuery({
    queryKey: ["catalog-tests", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/catalog/tests", { params: { query: { q: query || null, limit: 12 } } })),
    staleTime: 60_000,
  });
  const chosen = new Set(value.map((x) => x.id));
  const total = value.reduce((sum, x) => sum + (x.price ?? 0), 0);

  function add(test: Schemas["TestOut"]) {
    if (chosen.has(test.id)) return;
    onChange([...value, test]);
    setQ("");
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-sand-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("staff.tests.searchPlaceholder")}
            className="pl-10"
            autoFocus={autoFocus}
            data-testid="test-search"
            onKeyDown={(e) => {
              const first = results.data?.find((r) => !chosen.has(r.id));
              if (e.key === "Enter" && first) {
                e.preventDefault();
                add(first);
              }
            }}
          />
        </div>
        <ul className="mt-2 max-h-72 overflow-y-auto rounded-xl border border-sand-200 bg-white scrollbar-thin">
          {(results.data ?? []).map((test) => {
            const picked = chosen.has(test.id);
            return (
              <li key={test.id}>
                <button
                  type="button"
                  disabled={picked}
                  onClick={() => add(test)}
                  className={cn(
                    "flex w-full items-center gap-3 border-b border-sand-100 px-3.5 py-2.5 text-left last:border-0",
                    picked ? "opacity-40" : "hover:bg-brand-50/50",
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] font-semibold">
                      {lang === "bn" ? test.name_bn : test.name_en}
                    </span>
                    <span className="block truncate text-[12px] text-sand-500">
                      {test.code} · {test.department.name_en}
                      {test.fasting_required && ` · ${t("staff.tests.fasting")}`}
                    </span>
                  </span>
                  <span className="text-[13px] font-semibold tabular text-sand-700">{formatMoney(test.price, lang)}</span>
                  {!picked && <Plus className="size-4 text-brand-600" />}
                </button>
              </li>
            );
          })}
          {results.data?.length === 0 && (
            <li className="px-3.5 py-6 text-center text-[13px] text-sand-500">{t("common.noResults")}</li>
          )}
        </ul>
      </div>
      <div className="rounded-xl border border-dashed border-sand-300 bg-sand-50/50 p-3">
        <div className="mb-2 flex items-center justify-between text-[12px] font-semibold uppercase tracking-wider text-sand-500">
          <span>{t("staff.tests.selected", { count: value.length })}</span>
          <span className="tabular text-ink">{formatMoney(total, lang)}</span>
        </div>
        {value.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-sand-500">{t("staff.tests.none")}</p>
        ) : (
          <ul className="space-y-1.5" data-testid="selected-tests">
            {value.map((test) => (
              <li key={test.id} className="flex items-center gap-2 rounded-lg bg-white px-3 py-2 ring-1 ring-sand-200">
                <Badge tone="brand">{test.abbreviation}</Badge>
                <span className="min-w-0 flex-1 truncate text-[13.5px]">{lang === "bn" ? test.name_bn : test.name_en}</span>
                <span className="text-[13px] tabular text-sand-600">{formatMoney(test.price, lang)}</span>
                <button
                  type="button"
                  aria-label={t("common.remove")}
                  className="rounded-md p-1 text-sand-400 hover:bg-danger-50 hover:text-danger-600"
                  onClick={() => onChange(value.filter((x) => x.id !== test.id))}
                >
                  <X className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

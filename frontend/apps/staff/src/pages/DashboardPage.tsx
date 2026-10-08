import { unwrap } from "@bmu/api-client";
import { formatNumber, useI18n } from "@bmu/i18n";
import { Callout, Card, PageHeader, Stat } from "@bmu/ui";
import { useQuery } from "@tanstack/react-query";
import { AlarmClock, ArrowRight, ClipboardCheck, Info, MessageCircleQuestion, Wallet } from "lucide-react";
import { Link } from "react-router-dom";

import { NAV } from "../layout/nav";
import { api } from "../lib/api";
import { useSession } from "../lib/session";

export function DashboardPage() {
  const { t, lang } = useI18n();
  const { me, can } = useSession();
  const stats = useQuery({
    queryKey: ["order-stats"],
    queryFn: () => unwrap(api.GET("/api/v1/staff/orders/stats")),
    enabled: can("order.view", "order.verify", "order.lookup"),
    refetchInterval: 30_000,
  });
  const s = stats.data ?? {};
  const n = (k: string) => formatNumber(s[k] ?? 0, lang);
  const actions = NAV.flatMap((g) => g.items).filter((i) => i.path !== "/" && !i.milestone && can(...i.perms));

  return (
    <div>
      <PageHeader
        eyebrow={me?.station || t("nav.noStation")}
        title={t("staff.dashboard.greeting", { name: me?.full_name ?? "" })}
        subtitle={t("staff.dashboard.subtitle")}
      />
      {stats.data && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label={t("enums.orderStatus.PENDING_VERIFICATION")} value={n("PENDING_VERIFICATION")} icon={<ClipboardCheck className="size-4" />} tone="info" />
          <Stat
            label={t("staff.dashboard.overdue")}
            value={n("OVERDUE_VERIFICATION")}
            icon={<AlarmClock className="size-4" />}
            tone={(s.OVERDUE_VERIFICATION ?? 0) > 0 ? "danger" : "neutral"}
          />
          <Stat label={t("enums.orderStatus.NEEDS_CLARIFICATION")} value={n("NEEDS_CLARIFICATION")} icon={<MessageCircleQuestion className="size-4" />} tone="warn" />
          <Stat label={t("enums.orderStatus.AWAITING_PAYMENT")} value={n("AWAITING_PAYMENT")} icon={<Wallet className="size-4" />} tone="violet" />
        </div>
      )}
      <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-sand-500">{t("staff.dashboard.quick")}</h2>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {actions.map((item) => (
          <Link key={item.key} to={item.path}>
            <Card className="group flex items-center gap-4 p-4 transition hover:-translate-y-0.5 hover:shadow-lift">
              <span className="grid size-11 place-items-center rounded-xl bg-brand-50 text-brand-700">
                <item.icon className="size-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{t(`nav.items.${item.key}`)}</span>
                <span className="block truncate text-[13px] text-sand-500">{t(`staff.dashboard.hints.${item.key}`)}</span>
              </span>
              <ArrowRight className="size-4 text-sand-300 transition group-hover:translate-x-0.5 group-hover:text-brand-600" />
            </Card>
          </Link>
        ))}
      </div>
      <Callout tone="info" icon={<Info className="size-4" />} className="mt-8">
        {t("common.placeholderData")}
      </Callout>
    </div>
  );
}

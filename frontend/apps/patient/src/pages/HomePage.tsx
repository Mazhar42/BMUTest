import { useI18n } from "@bmu/i18n";
import { cn } from "@bmu/ui";
import { CalendarCheck2, ChevronRight, FileText, LogOut, TestTubeDiagonal } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Screen } from "../components/Layout";
import { logout } from "../lib/api";
import { useSession } from "../lib/session";

function BigButton({
  to,
  icon,
  title,
  body,
  primary,
  testId,
}: {
  to: string;
  icon: ReactNode;
  title: string;
  body: string;
  primary?: boolean;
  testId?: string;
}) {
  return (
    <Link
      to={to}
      data-testid={testId}
      className={cn(
        "flex items-center gap-4 rounded-3xl p-5 shadow-card ring-1 transition active:scale-[0.99]",
        primary ? "bg-brand-600 text-white ring-brand-700" : "bg-white text-ink ring-sand-200",
      )}
    >
      <span className={cn("grid size-14 shrink-0 place-items-center rounded-2xl", primary ? "bg-white/15" : "bg-brand-50 text-brand-700")}>
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[19px] font-bold">{title}</span>
        <span className={cn("mt-0.5 block text-[14px]", primary ? "text-white/75" : "text-sand-600")}>{body}</span>
      </span>
      <ChevronRight className={cn("size-5", primary ? "text-white/70" : "text-sand-400")} />
    </Link>
  );
}

/** Home: three buttons, nothing else (ROADMAP §5.1 step 2). */
export function HomePage() {
  const { t } = useI18n();
  const { account } = useSession();
  const self = account?.patients.find((p) => p.relation_to_account === "SELF");
  return (
    <Screen title={t("common.appName")}>
      <div className="pt-4">
        <p className="text-[15px] text-sand-600">{t("patient.home.hello")}</p>
        <h2 className="text-[26px] font-bold leading-tight">{self?.full_name ?? t("patient.home.welcome")}</h2>
      </div>
      <div className="mt-6 grid gap-4">
        <BigButton
          to="/book"
          primary
          icon={<TestTubeDiagonal className="size-7" />}
          title={t("patient.home.book")}
          body={t("patient.home.bookBody")}
          testId="home-book"
        />
        <BigButton
          to="/orders"
          icon={<CalendarCheck2 className="size-7" />}
          title={t("patient.home.appointments")}
          body={t("patient.home.appointmentsBody")}
          testId="home-orders"
        />
        <BigButton to="/reports" icon={<FileText className="size-7" />} title={t("patient.home.reports")} body={t("patient.home.reportsBody")} />
      </div>
      <button
        type="button"
        onClick={() => void logout()}
        className="mx-auto mt-10 flex items-center gap-2 text-[14px] font-semibold text-sand-500"
      >
        <LogOut className="size-4" /> {t("common.logout")}
      </button>
    </Screen>
  );
}

import { digits, useI18n } from "@bmu/i18n";
import { Button, cn, Skeleton } from "@bmu/ui";
import { ChevronRight, UserPlus, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { Screen } from "../components/Layout";
import { useSession } from "../lib/session";

/** "Who is this for?" — self or a family member (ROADMAP §5.1 step 3). */
export default function WhoForPage() {
  const { t, lang } = useI18n();
  const { account } = useSession();
  if (!account) return <Screen back="/" title={t("patient.whoFor.title")}><Skeleton className="mt-4 h-40" /></Screen>;
  const hasSelf = account.patients.some((p) => p.relation_to_account === "SELF");

  return (
    <Screen back="/" title={t("patient.whoFor.title")}>
      <p className="pt-2 text-[15px] text-sand-600">{t("patient.whoFor.subtitle")}</p>
      <ul className="mt-5 grid gap-3">
        {account.patients.map((p) => (
          <li key={p.id}>
            <Link
              to={`/book/${p.id}`}
              data-testid="who-patient"
              className="flex items-center gap-4 rounded-2xl bg-white p-4 shadow-card ring-1 ring-sand-200 active:scale-[0.99]"
            >
              <span
                className={cn(
                  "grid size-12 place-items-center rounded-full text-[18px] font-bold",
                  p.relation_to_account === "SELF" ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-700",
                )}
              >
                {p.full_name.slice(0, 1)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[17px] font-semibold">{p.full_name_bn && lang === "bn" ? p.full_name_bn : p.full_name}</span>
                <span className="block text-[14px] text-sand-500">
                  {t(`enums.relation.${p.relation_to_account}`)}
                  {p.age !== null && ` · ${t("common.years", { count: p.age }).replace(String(p.age), digits(p.age, lang))}`}
                </span>
              </span>
              <ChevronRight className="size-5 text-sand-400" />
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-5 grid gap-3">
        {!hasSelf && (
          <Link to="/family/new?self=1">
            <Button block size="xl" icon={<UserRound className="size-5" />} data-testid="add-self">
              {t("patient.whoFor.myself")}
            </Button>
          </Link>
        )}
        <Link to="/family/new">
          <Button block size="xl" variant="outline" icon={<UserPlus className="size-5" />}>
            {t("patient.whoFor.addFamily")}
          </Button>
        </Link>
      </div>
    </Screen>
  );
}

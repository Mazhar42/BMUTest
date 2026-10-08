import { useI18n } from "@bmu/i18n";
import { EmptyState } from "@bmu/ui";
import { FileText } from "lucide-react";

import { Screen } from "../components/Layout";

/** My Reports — report download, sharing and printed copies arrive with milestone M8. */
export default function ReportsPage() {
  const { t } = useI18n();
  return (
    <Screen back="/" title={t("patient.home.reports")}>
      <EmptyState icon={<FileText className="size-6" />} title={t("patient.reports.empty")} body={t("patient.reports.emptyBody")} />
    </Screen>
  );
}

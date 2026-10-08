import { useI18n } from "@bmu/i18n";
import { Card, EmptyState } from "@bmu/ui";

import type { NavItem } from "../layout/nav";

/** Screens planned for a later roadmap milestone. */
export function ComingSoonPage({ item }: { item: NavItem }) {
  const { t } = useI18n();
  return (
    <Card>
      <EmptyState
        icon={<item.icon className="size-6" />}
        title={t(`nav.items.${item.key}`)}
        body={t("staff.comingSoon", { milestone: item.milestone })}
      />
    </Card>
  );
}

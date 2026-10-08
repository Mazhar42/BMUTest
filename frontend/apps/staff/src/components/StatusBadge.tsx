import { useI18n } from "@bmu/i18n";
import { Badge, type Tone } from "@bmu/ui";

const ORDER_TONES: Record<string, Tone> = {
  DRAFT: "neutral",
  PENDING_VERIFICATION: "info",
  NEEDS_CLARIFICATION: "warn",
  AWAITING_PAYMENT: "violet",
  PAID: "ok",
  READY_FOR_COLLECTION: "brand",
  CHECKED_IN: "brand",
  COLLECTED: "brand",
  IN_LAB: "brand",
  COMPLETED: "ok",
  REJECTED: "danger",
  EXPIRED: "neutral",
  CANCELLED: "neutral",
  REFUND_PENDING: "warn",
  REFUNDED: "neutral",
};

export function OrderStatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  return (
    <Badge tone={ORDER_TONES[status] ?? "neutral"} dot>
      {t(`enums.orderStatus.${status}`)}
    </Badge>
  );
}

const WAIVER_TONES: Record<string, Tone> = { REQUESTED: "warn", APPROVED: "ok", DECLINED: "danger", WITHDRAWN: "neutral" };

export function WaiverStatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  return <Badge tone={WAIVER_TONES[status] ?? "neutral"}>{t(`enums.waiverStatus.${status}`)}</Badge>;
}

export function PriorityBadge({ priority }: { priority: string }) {
  const { t } = useI18n();
  if (priority === "NORMAL") return null;
  return <Badge tone={priority === "EMERGENCY" ? "danger" : "info"}>{t(`enums.priority.${priority}`)}</Badge>;
}

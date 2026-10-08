# 0005 — Fee categories and waivers

**Status:** accepted (M3)

## Context
ROADMAP §5.4: the help desk sets a fee category (free / poor fund / staff / concession); a user with
`waiver.approve` approves it with a reason, creating a `WAIVER` payment. How much a concession is worth
is institutional policy we must not invent.

## Decision
- Every order item snapshots the **GENERAL** price. A non-GENERAL category opens a `WaiverRequest`
  (its own state machine: REQUESTED → APPROVED | DECLINED | WITHDRAWN) instead of changing prices.
- The approver enters the **discount amount** explicitly (≤ remaining total) and a reason. Approval sets the
  order's fee category, reduces `total`, and records a `WAIVER` payment (status SUCCESS) for the discount.
  A total of 0 moves the order to PAID.
- The requester can never approve their own request, even if they hold `waiver.approve`.

## Consequences
Per-category price lists (`lab_test_price.fee_category`) remain available for later if BMU prefers fixed
staff/concession prices **[BMU]**. Emergency is a priority, not a fee category.

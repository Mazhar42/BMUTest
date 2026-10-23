# 0006 — Payments: provider adapters, settlement rules, refunds

**Status:** accepted (M4)

## Context
ROADMAP §7.4/§9: one order can be paid at a bank booth, at a hospital counter or online. Duplicate callbacks, two tellers
clicking at once and a wrong gateway amount must never double-count or lose money. Refund policy and MDR are **[BMU]**
decisions we must not invent.

## Decision
- **Adapter interface** (`initiate`, `validate`, `query`, `refund`) with a `mock` provider (dev/tests/E2E, off in prod) and
  SSLCommerz. Teller / counter / waiver are internal methods without an adapter.
- **Settlement is one function** (`apply_validation`) used by the IPN, the patient's status poll and the Beat re-query. It
  locks the payment row, records the raw event, ignores repeats, and only on a provider-verified result with matching
  `tran_id`, amount and currency moves the payment to SUCCESS and the order to PAID. Unique `(provider, provider_txn_id)`
  stops one gateway transaction from settling two payments.
- **In-person receipts lock the order row first** (`SELECT … FOR UPDATE`), so concurrent tellers produce exactly one SUCCESS;
  the loser gets `ORDER_ALREADY_PAID` with who/how/when and the token. Tested with real parallel sessions.
- **No silent money:** a confirmed payment for an order that no longer needs it creates a system **refund request**. A late
  gateway confirmation is allowed after EXPIRED or CANCELLED for the same reason.
- **Refunds are full-amount, two-person:** requester ≠ approver, manual mode needs a reference, gateway mode only for gateway
  payments, a failed provider call stays retryable. An order returns to PAID if a refund is rejected (new transition).
- **Tokens:** `queue_token` (W for normal, P for emergency) is issued in the same transaction as the receipt from an atomic
  daily counter; M5 builds calling, A-tokens and the display on the same table.
- **Reconciliation** matches teller payments by order code (check-digit verified) or receipt number plus amount;
  lines are fingerprinted so overlapping statements are idempotent.

## Consequences
- Partial payments and partial refunds are not supported (the order amount is paid in one go) — add when BMU asks.
- Gateway settlement-report reconciliation (the gateway's own CSV) is not built; only bank statements are. Online payments are
  marked reconciled through the gateway's validation, not a settlement file **[BMU]**.
- Refund approval rights sit with LAB_ADMIN/SUPER_ADMIN; BMU may want a dedicated role.

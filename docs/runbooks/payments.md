# Runbook — payments

Design: [ADR 0006](../adr/0006-payments.md). Code: `backend/app/modules/payments/`.

## How money reaches an order

| Channel | Who | Result |
|---|---|---|
| **Bank teller** (`/teller`) | Scans/types the code from the bank copy, checks name and amount, "Received" | Payment `BANK_TELLER` SUCCESS → order PAID → **W/P token issued and sent by SMS immediately** |
| **Counter cash** (`/cashier`) | Hospital cashier, only if `COUNTER_PAYMENT_ENABLED=true` (Settings) | Same, method `COUNTER_CASH` |
| **Online** (patient app) | bKash / Nagad / Upay / Rocket / card through the gateway | Payment `GATEWAY`; order PAID when the gateway-verified callback matches |
| **Waiver** | Waiver approver (M3) | `WAIVER` payment for the discount; the rest is paid as above |

Teller screen states: **Ready to receive**, **ALREADY PAID** (shows who/how/when and the token — never take money again),
**NOT VERIFIED YET**, **EXPIRED**, **CLOSED**. A mistyped code is rejected by its check digit.

Settings (in `.env`; runtime overrides without a redeploy come with the settings screen in M9): `TELLER_REQUIRE_RECEIPT_NO`, `COUNTER_PAYMENT_ENABLED`, `ORDER_EXPIRY_DAYS`,
`PAYMENT_PENDING_REQUERY_MINUTES` (10), `PAYMENT_PENDING_EXPIRE_HOURS` (24), `PAYMENT_CURRENCY` (BDT).

## Day close

`Teller → Day close`: count, total, refunded and net for the signed-in teller for today (Asia/Dhaka); **Print** uses the
browser print dialog. The total always equals the sum of the listed payments. Users with `payment.view` can read any
teller's close through the API (`GET /api/v1/staff/payments/day-close?staff_id=…&day=YYYY-MM-DD`).

## Refunds

1. Cashier / lab admin: **Refunds → find the order → Request refund** (reason required). The payment becomes
   `REFUND_PENDING`; if no other payment covers the order, the order becomes `REFUND_PENDING` too.
2. A **different** user with `payment.refund.approve` (LAB_ADMIN / SUPER_ADMIN) approves:
   - *Manual* — cash handed back or bank transfer; the voucher/transfer reference is mandatory.
   - *Through the gateway* — only for online payments; calls the provider refund API. If the gateway refuses, the refund
     is `FAILED`, the payment stays `REFUND_PENDING`, and it can be retried or done manually.
3. Completed: payment `REFUNDED`, order `REFUNDED`, the queue token is cancelled, the patient gets an SMS.
4. Rejecting restores the payment (`SUCCESS`) and the order (`PAID`).

**Automatic refund requests.** If the gateway confirms money for an order that no longer needs it (the patient also paid at
the bank, or the order was cancelled/expired), the system raises a refund request (reason `DUPLICATE_PAYMENT` /
`ORDER_NOT_PAYABLE`) so the money is never silently kept. These appear in the same queue marked *Automatic*.

## Reconciliation (bank statement CSV)

`Reconciliation → Upload`: give the bank name and the column names (date, credit, narration, optional receipt) and the date
format (e.g. `%d/%m/%Y`); the mapping is remembered per bank. Lines are matched to teller payments by the order code written in
the narration (any format, check digit verified) — or by receipt number — **and** amount. Results:

- **Matched** — payment marked reconciled.
- **No payment found** / **Amount differs** / **Already matched** — shown in *Exceptions*; resolve with a note.
- Debits and blank amounts are skipped. Re-uploading an overlapping statement skips lines already imported.
- The nightly job (`auto_reconcile`) re-tries lines that had no payment yet (e.g. back-entered receipts).

## Gateway: SSLCommerz

Needs **[BMU]** a merchant account in BMU's own name with settlement to BMU's bank account, and a **publicly reachable HTTPS**
endpoint for the IPN. Settings in `.env`:

```
PAYMENT_PROVIDER=sslcommerz
SSLCOMMERZ_STORE_ID=...
SSLCOMMERZ_STORE_PASSWORD=...
SSLCOMMERZ_SANDBOX=true          # false only with live credentials
PUBLIC_BASE_URL=https://lab.example.org
```

The code never trusts a callback: the IPN is verified with the **Validation API** (`val_id`), then `tran_id`, amount and
currency are compared with our payment (mismatch → payment `FAILED` with reason `AMOUNT_MISMATCH` / `TRAN_ID_MISMATCH` /
`CURRENCY_MISMATCH`). The browser success/fail/cancel redirects only send the patient back to the result page, which asks our
server for the status; a `PENDING` payment is re-checked with the gateway (every poll, and a Beat job every 2 minutes for
payments older than 10 minutes). Payments with no confirmation after 24 h become `EXPIRED`; a late valid confirmation still
settles (and is refunded if not needed).

### Sandbox round trip (do this once credentials exist)

1. Register at the SSLCommerz sandbox and note the store id and password. Put them in `.env` with `SSLCOMMERZ_SANDBOX=true`.
2. The IPN must be reachable from the internet. Locally: `cloudflared tunnel --url http://localhost:5173` (or ngrok) and set
   `PUBLIC_BASE_URL` to the tunnel URL; in the SSLCommerz sandbox panel set the IPN URL to
   `<PUBLIC_BASE_URL>/api/v1/public/payments/sslcommerz/ipn`.
3. `make up && make migrate && make seed`, restart the API so it reads `.env`.
4. Create and verify an order (patient app → verifier), open it in the patient app, press **bKash** (or any method).
5. On the SSLCommerz sandbox page use the test card/wallet from SSLCommerz's sandbox documentation and complete the payment.
6. You are returned to `/pay/result`; within a few seconds it shows *Payment received*. In the staff app the order shows
   `Paid`, and the payment has a provider transaction id. Check `payment_event` for the raw `ipn` and `requery` events.
7. Repeat with a failed payment and a cancelled payment; both leave the order `Awaiting payment` so the patient can retry.
8. Test a refund: Refunds → request → approve **Through the payment gateway**. In the sandbox the refund call returns
   `success`/`processing`; the refund then shows *Refunded*.

> Status: the adapter is covered by automated tests against a mocked HTTP transport (`backend/tests/api/test_m4_payments.py`)
> and the whole flow by the built-in mock gateway (E2E). The live sandbox round trip above has **not** been run yet: it needs
> BMU's/the team's sandbox credentials (open item in PROGRESS.md).

## Mock gateway (development and E2E only)

With `PAYMENT_PROVIDER=mock` (default) the patient app's "Pay" opens a page served by our API
(`/api/v1/public/payments/mock/<tran_id>`) with *Pay now / Simulate failure / Cancel*. It is **disabled when `ENV=prod`**, and
then `online_payments` is `false` in `/api/v1/public/payments/config`, so the patient app only offers "Pay at the hospital".

## Stuck or odd payments

| Symptom | What to do |
|---|---|
| Patient says "I paid online" but the order is still *Awaiting payment* | Open **Refunds → find order**: look at the payment. `PENDING` → wait for the re-query, or ask the patient to reopen the app (the result page re-checks). Still unknown after 24 h → check the gateway merchant panel by the transaction id. |
| Payment `FAILED` with `AMOUNT_MISMATCH` | Money may still have moved at the gateway. Compare in the merchant panel; refund there or manually, and record it. |
| Reconciliation exception *Amount differs* | The teller keyed a different amount than the bank received. Resolve with a note after checking the bank copy. |
| Teller says "ALREADY PAID" but the patient has no token | Open the order (Orders → code); the token shows on the teller screen. Reprint it there. |

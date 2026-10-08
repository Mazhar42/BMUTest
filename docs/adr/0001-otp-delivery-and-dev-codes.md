# 0001 — OTP delivery and development codes

**Status:** accepted (M2)

## Context
Patient login is a 6-digit SMS code (ROADMAP §6.4). Ordinary SMS goes through the outbox table and a
Celery job with retries (§9). An OTP is time-critical (5-minute TTL) and is a secret. Developers and the
Playwright suite also need to log in without a real SMS provider.

## Decision
- OTPs are sent **synchronously** in the request through the `SmsProvider` adapter, not through the
  outbox. A `notification` row is still written for the audit trail, with the code replaced by `***`.
- Only an HMAC of `mobile:code` is stored (`otp_challenge.code_hash`). Requesting a new code invalidates
  older unused ones. Rate limits: 3 sends / 15 min per mobile, 20 per IP; 5 wrong attempts burn the code.
- When `ENV != prod` **and** `SMS_PROVIDER=mock`, `/otp/request` returns the code as `debug_code`, the
  patient app shows it ("Test mode — your code is …") and the mock provider prints it to the container log.
  `ENV=prod` never returns it, whatever the SMS provider.

## Consequences
- No OTP plaintext is ever persisted; a slow SMS provider slows the login request (acceptable at pilot load).
- **[BMU]** Production logins require a real SMS provider (`SMS_PROVIDER=sslwireless` + credentials).

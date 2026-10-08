# 0002 — Help-desk patients are not linked to app accounts automatically

**Status:** accepted (M2)

## Context
A patient registered at the help desk may later log in with OTP using the same mobile number. Linking
automatically by mobile would show that patient's orders to whoever controls the number (often a
relative's phone), which is a privacy risk.

## Decision
Help-desk registrations have `account_id = NULL`. App accounts only see patients they created themselves.
The staff search shows whether a patient "uses the app" or is "help desk only". A deliberate, verified
"claim this patient" flow can be added later (open question in PROGRESS.md).

## Consequences
A walk-in patient who later installs the app does not see earlier help-desk orders yet. SMS still reaches
them with the order code, and staff can find everything by mobile or code.

/** Formatting that follows the UI language: Bangla numerals in bn (৳১,২৫০), South-Asian digit grouping
 *  (1,25,000), dates/times always in Asia/Dhaka. Money is integer paisa everywhere. */

export type Lang = "bn" | "en";

export const TZ = "Asia/Dhaka";
const BN_DIGITS = ["০", "১", "২", "৩", "৪", "৫", "৬", "৭", "৮", "৯"];

export function toBnDigits(s: string): string {
  return s.replace(/[0-9]/g, (d) => BN_DIGITS[Number(d)] ?? d);
}

export function digits(s: string | number, lang: Lang): string {
  const str = String(s);
  return lang === "bn" ? toBnDigits(str) : str;
}

/** 1250000 -> "12,50,000" */
export function groupSouthAsian(intPart: string): string {
  const neg = intPart.startsWith("-");
  const n = neg ? intPart.slice(1) : intPart;
  if (n.length <= 3) return (neg ? "-" : "") + n;
  const last3 = n.slice(-3);
  const rest = n.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${neg ? "-" : ""}${rest},${last3}`;
}

export function formatNumber(n: number, lang: Lang, fractionDigits = 0): string {
  const fixed = Math.abs(n).toFixed(fractionDigits);
  const [i = "0", f] = fixed.split(".");
  const s = (n < 0 ? "-" : "") + groupSouthAsian(i) + (f ? `.${f}` : "");
  return digits(s, lang);
}

export function formatMoney(paisa: number | null | undefined, lang: Lang): string {
  if (paisa === null || paisa === undefined) return "—";
  const hasFraction = paisa % 100 !== 0;
  return `৳${formatNumber(paisa / 100, lang, hasFraction ? 2 : 0)}`;
}

function locale(lang: Lang): string {
  return lang === "bn" ? "bn-BD" : "en-GB";
}

function asDate(v: string | Date): Date {
  return typeof v === "string" ? new Date(v) : v;
}

export function formatDate(v: string | Date | null | undefined, lang: Lang, style: "short" | "long" = "long"): string {
  if (!v) return "—";
  // A bare YYYY-MM-DD is a calendar date — render it without a timezone shift.
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const [y, m, d] = v.split("-").map(Number);
    return new Intl.DateTimeFormat(locale(lang), {
      timeZone: "UTC",
      day: "numeric",
      month: style === "long" ? "long" : "short",
      year: "numeric",
      weekday: style === "long" ? "short" : undefined,
    }).format(new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)));
  }
  return new Intl.DateTimeFormat(locale(lang), {
    timeZone: TZ,
    day: "numeric",
    month: style === "long" ? "long" : "short",
    year: "numeric",
  }).format(asDate(v));
}

export function formatTime(v: string | Date | null | undefined, lang: Lang): string {
  if (!v) return "—";
  if (typeof v === "string" && /^\d{2}:\d{2}(:\d{2})?$/.test(v)) {
    const [h = 0, m = 0] = v.split(":").map(Number);
    return new Intl.DateTimeFormat(locale(lang), { timeZone: "UTC", hour: "numeric", minute: "2-digit" }).format(
      new Date(Date.UTC(2000, 0, 1, h, m)),
    );
  }
  return new Intl.DateTimeFormat(locale(lang), { timeZone: TZ, hour: "numeric", minute: "2-digit" }).format(asDate(v));
}

export function formatDateTime(v: string | Date | null | undefined, lang: Lang): string {
  if (!v) return "—";
  return new Intl.DateTimeFormat(locale(lang), {
    timeZone: TZ,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(asDate(v));
}

export function formatRelative(v: string | Date | null | undefined, lang: Lang, now: Date = new Date()): string {
  if (!v) return "—";
  const diffSec = Math.round((asDate(v).getTime() - now.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale(lang), { numeric: "auto" });
  const abs = Math.abs(diffSec);
  if (abs < 60) return rtf.format(diffSec, "second");
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
  return rtf.format(Math.round(diffSec / 86400), "day");
}

/** Today's date in Dhaka as YYYY-MM-DD. */
export function dhakaToday(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" })
    .format(now);
  return parts;
}

/** Mask a mobile number for display: +8801712345678 -> 01712•••678 */
export function maskMobile(mobile: string | null | undefined): string {
  if (!mobile) return "—";
  const local = mobile.replace(/^\+?880/, "0");
  return `${local.slice(0, 5)}•••${local.slice(-3)}`;
}

export function localMobile(mobile: string | null | undefined): string {
  return mobile ? mobile.replace(/^\+?880/, "0") : "";
}

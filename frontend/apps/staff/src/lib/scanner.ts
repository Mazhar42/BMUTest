import { useEffect, useRef } from "react";

/** USB barcode scanners type like a keyboard: a fast burst of characters ending with Enter.
 *  `useScanner(onScan)` listens globally and calls `onScan(text)` for bursts whose keystrokes arrive
 *  less than `maxGapMs` apart. Typing by hand into normal inputs is unaffected. */
export function useScanner(
  onScan: (value: string) => void,
  { enabled = true, minLength = 6, maxGapMs = 35 }: { enabled?: boolean; minLength?: number; maxGapMs?: number } = {},
): void {
  const handler = useRef(onScan);
  handler.current = onScan;

  useEffect(() => {
    if (!enabled) return;
    let buffer = "";
    let last = 0;
    let fastStreak = 0;

    function onKey(e: KeyboardEvent) {
      const now = performance.now();
      const gap = now - last;
      last = now;
      if (e.key === "Enter") {
        const value = buffer;
        const looksScanned = value.length >= minLength && fastStreak >= value.length - 2;
        buffer = "";
        fastStreak = 0;
        if (looksScanned) {
          const target = e.target as HTMLElement | null;
          // In a dedicated scan field the field's own submit handles it.
          if (target?.dataset?.scanField === "true") return;
          e.preventDefault();
          handler.current(value);
        }
        return;
      }
      if (e.key.length !== 1 || e.ctrlKey || e.metaKey || e.altKey) return;
      if (gap > 300) {
        buffer = "";
        fastStreak = 0;
      }
      buffer += e.key;
      if (gap <= maxGapMs) fastStreak += 1;
    }

    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [enabled, minLength, maxGapMs]);
}

/** Classify a scanned/typed value: 14 digits = tube accession, 12 digits = order code. */
export function classifyScan(raw: string): { kind: "order" | "accession" | "token" | "unknown"; value: string } {
  const digits = raw.replace(/[\s\-–—·T]/g, "");
  if (/^\d{14}$/.test(digits)) return { kind: "accession", value: digits };
  if (/^\d{12}$/.test(digits)) return { kind: "order", value: digits };
  if (/^[AWP]-?\d{1,4}$/i.test(raw.trim())) return { kind: "token", value: raw.trim().toUpperCase() };
  return { kind: "unknown", value: raw.trim() };
}

import { flatKeys, resources } from "./resources";

const NAMESPACES = Object.keys(resources.en).join("|");

/** Translation keys referenced in source files that are missing from the English resources.
 *  Checks every string literal that starts with a namespace ("staff.verify.confirm") and every
 *  template-literal prefix used with t() (`enums.orderStatus.${s}` → "enums.orderStatus"). */
export function missingKeys(sources: Record<string, string>, ignore: string[] = []): string[] {
  const keys = flatKeys(resources.en);
  const known = new Set(keys);
  const literal = new RegExp(String.raw`["'](` + `(?:${NAMESPACES})` + String.raw`\.[A-Za-z0-9_.]+)["']`, "g");
  const prefix = new RegExp(String.raw`\bt\(\s*` + "`" + `((?:${NAMESPACES})` + String.raw`\.[A-Za-z0-9_.]+)\.\$\{`, "g");
  const missing = new Set<string>();
  for (const [file, src] of Object.entries(sources)) {
    for (const m of src.matchAll(literal)) {
      const key = m[1]!;
      if (ignore.includes(key)) continue;
      if (!known.has(key) && !keys.some((k) => k.startsWith(`${key}.`))) missing.add(`${file}: ${key}`);
    }
    for (const m of src.matchAll(prefix)) {
      const p = m[1]!;
      if (!keys.some((k) => k.startsWith(`${p}.`))) missing.add(`${file}: ${p}.*`);
    }
  }
  return [...missing].sort();
}

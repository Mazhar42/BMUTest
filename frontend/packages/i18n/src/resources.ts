/** Translations live in per-feature files: locales/{en,bn}/<feature>.json, merged here. */
type Tree = { [key: string]: string | Tree };

const en = import.meta.glob<Tree>("./locales/en/*.json", { eager: true, import: "default" });
const bn = import.meta.glob<Tree>("./locales/bn/*.json", { eager: true, import: "default" });

function merge(files: Record<string, Tree>): Tree {
  const out: Tree = {};
  for (const [path, tree] of Object.entries(files)) {
    const ns = path.split("/").pop()!.replace(/\.json$/, "");
    out[ns] = tree;
  }
  return out;
}

export const resources = { en: merge(en), bn: merge(bn) };

export function flatKeys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : flatKeys(v, `${prefix}${k}.`),
  );
}

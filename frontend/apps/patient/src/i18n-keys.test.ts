import { missingKeys } from "@bmu/i18n";
import { describe, expect, it } from "vitest";

const sources = import.meta.glob<string>(["./**/*.tsx", "./**/*.ts", "!./**/*.test.ts"], {
  query: "?raw",
  import: "default",
  eager: true,
});

describe("patient app translations", () => {
  it("every key used in the source exists", () => {
    expect(missingKeys(sources)).toEqual([]);
  });
});

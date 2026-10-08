import { missingKeys } from "@bmu/i18n";
import { describe, expect, it } from "vitest";

const sources = import.meta.glob<string>(["./**/*.tsx", "./**/*.ts", "!./**/*.test.ts"], {
  query: "?raw",
  import: "default",
  eager: true,
});

describe("staff app translations", () => {
  it("every key used in the source exists", () => {
    // permission strings that happen to start with a namespace name
    expect(missingKeys(sources, ["staff.manage", "patient.search", "patient.view", "patient.register"])).toEqual([]);
  });
});

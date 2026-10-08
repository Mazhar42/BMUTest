import { describe, expect, it } from "vitest";

import { formatMoney, formatNumber, groupSouthAsian, toBnDigits } from "./format";
import { flatKeys, resources } from "./resources";

describe("translations", () => {
  it("bn and en have exactly the same keys", () => {
    const en = new Set(flatKeys(resources.en));
    const bn = new Set(flatKeys(resources.bn));
    expect([...en].filter((k) => !bn.has(k))).toEqual([]);
    expect([...bn].filter((k) => !en.has(k))).toEqual([]);
  });
});

describe("format", () => {
  it("groups digits the South-Asian way", () => {
    expect(groupSouthAsian("1250")).toBe("1,250");
    expect(groupSouthAsian("1250000")).toBe("12,50,000");
    expect(formatNumber(123456789, "en")).toBe("12,34,56,789");
  });
  it("formats money in paisa with language numerals", () => {
    expect(formatMoney(125000, "en")).toBe("৳1,250");
    expect(formatMoney(125000, "bn")).toBe("৳১,২৫০");
    expect(formatMoney(125050, "en")).toBe("৳1,250.50");
    expect(toBnDigits("2026")).toBe("২০২৬");
  });
});

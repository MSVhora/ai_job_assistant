import { describe, expect, it } from "vitest";

import { formatUsd } from "./format-cost";

describe("formatUsd", () => {
  it("shows four decimals for sub-cent amounts", () => {
    expect(formatUsd(0.00158)).toBe("$0.0016");
  });

  it("shows cents for larger amounts", () => {
    expect(formatUsd(0.5)).toBe("$0.50");
  });

  it("collapses negligible and zero amounts", () => {
    expect(formatUsd(0.00001)).toBe("<$0.0001");
    expect(formatUsd(0)).toBe("$0");
  });
});

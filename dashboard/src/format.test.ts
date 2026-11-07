import { expect, it } from "vitest";
import { day, money, sentenceCase } from "./format";
import { parseRoute } from "./hooks";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
  expect(money(61.5)).toBe("$61.50");
});

it("formats dates and names", () => {
  expect(day("2026-06-24")).toBe("Jun 24, 2026");
  expect(sentenceCase("emergency_medical")).toBe("Emergency medical");
});

it("parses routes", () => {
  expect(parseRoute("")).toEqual({ page: "queue" });
  expect(parseRoute("#/")).toEqual({ page: "queue" });
  expect(parseRoute("#/claims/CLM-1001")).toEqual({
    page: "claim",
    claimId: "CLM-1001",
  });
  expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
  expect(parseRoute("#/nowhere")).toEqual({ page: "queue" });
});

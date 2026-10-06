import { describe, expect, it } from "vitest";

import { citation } from "@/components/features/chat/fixtures";

import { answerWithCitations, plainAnswer, splitAnswer, STARTERS } from "./agent-view";

describe("agent view helpers", () => {
  it("splits an answer into text and citation markers", () => {
    expect(splitAnswer("I cut it to 9 minutes [A1][E2]. Then more.")).toEqual([
      { kind: "text", text: "I cut it to 9 minutes " },
      { kind: "marker", marker: "A1" },
      { kind: "marker", marker: "E2" },
      { kind: "text", text: ". Then more." },
    ]);
  });

  it("returns the whole text when there are no markers", () => {
    expect(splitAnswer("Nothing cited here.")).toEqual([
      { kind: "text", text: "Nothing cited here." },
    ]);
  });

  it("strips markers and the space they leave before punctuation", () => {
    expect(plainAnswer("I batched the writes [A1] [E1]. It worked [P].")).toBe(
      "I batched the writes. It worked.",
    );
  });

  it("appends the cited sources for the copy-with-citations format", () => {
    const text = answerWithCitations("I did it.", [
      citation("A1", { quote: "Cut the import", url: "https://example.com/pr/1" }),
      citation("E1"),
    ]);

    expect(text).toBe(
      "I did it.\n\nSources:\n1. Source A1: Cut the import (https://example.com/pr/1)\n2. Source E1",
    );
    expect(answerWithCitations("I did it.", [])).toBe("I did it.");
  });

  it("offers general starter questions, none tied to a mode", () => {
    expect(STARTERS.map((starter) => starter.label)).toEqual([
      "Tell me about yourself",
      "What have I built with Python?",
      "Summarise my last two years",
    ]);
  });
});

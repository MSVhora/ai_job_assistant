import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { exportResumeDocument } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ExportMenu } from "./ExportMenu";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  exportResumeDocument: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const writeText = vi.fn<(text: string) => Promise<void>>();

beforeEach(() => {
  vi.resetAllMocks();
  writeText.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

describe("ExportMenu", () => {
  it.each([
    ["Plain text", "text"],
    ["Markdown", "markdown"],
    ["JSON Resume", "json_resume"],
  ] as const)("copies the clean %s export from the backend", async (label, format) => {
    vi.mocked(exportResumeDocument).mockResolvedValue(`exported as ${format}`);
    renderWithClient(<ExportMenu documentId="d1" />);

    await userEvent.click(
      screen.getByRole("button", { name: `Copy the whole resume as ${label}` }),
    );

    expect(exportResumeDocument).toHaveBeenCalledWith("d1", format);
    expect(writeText).toHaveBeenCalledWith(`exported as ${format}`);
  });
});

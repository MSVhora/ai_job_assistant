import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getTokenCheck } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ConnectStatus } from "./ConnectStatus";
import { status } from "./fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getTokenCheck: vi.fn(),
}));

const check = (overrides: Partial<Awaited<ReturnType<typeof getTokenCheck>>> = {}) => ({
  login: "ada",
  token_type: "classic" as const,
  scopes: ["repo"],
  private_access: true,
  warnings: [],
  ...overrides,
});

describe("ConnectStatus token check", () => {
  beforeEach(() => {
    vi.mocked(getTokenCheck).mockReset();
  });

  it("warns when a classic token cannot read private repositories", async () => {
    vi.mocked(getTokenCheck).mockResolvedValue(
      check({
        scopes: ["public_repo"],
        private_access: false,
        warnings: [
          "This classic token lacks the top-level `repo` scope, so private repositories are hidden.",
        ],
      }),
    );
    renderWithClient(<ConnectStatus status={status()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/lacks the top-level `repo` scope/);
  });

  it("shows nothing extra for a healthy token", async () => {
    vi.mocked(getTokenCheck).mockResolvedValue(check());
    renderWithClient(<ConnectStatus status={status()} />);

    await screen.findByText("Token configured");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not check a token that is not configured", () => {
    renderWithClient(<ConnectStatus status={status({ configured: false })} />);

    expect(getTokenCheck).not.toHaveBeenCalled();
    expect(screen.getByText("Token missing")).toBeInTheDocument();
  });

  it("stays quiet when the check itself fails", async () => {
    vi.mocked(getTokenCheck).mockRejectedValue(new Error("boom"));
    renderWithClient(<ConnectStatus status={status()} />);

    await screen.findByText("Token configured");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

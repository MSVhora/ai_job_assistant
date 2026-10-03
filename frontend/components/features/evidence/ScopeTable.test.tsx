"use client";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listEmployers, listGithubScopes, updateGithubScopes } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { scope, status } from "./fixtures";
import { ScopeTable } from "./ScopeTable";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  listGithubScopes: vi.fn(),
  updateGithubScopes: vi.fn(),
  listEmployers: vi.fn(),
}));

const EMPLOYERS = [
  {
    kind: "experience" as const,
    label: "Acme Corp (Mar 2021)",
    company: "Acme Corp",
    start_date: "Mar 2021",
  },
  { kind: "personal" as const, label: "Personal / open source", company: null, start_date: null },
];

describe("ScopeTable", () => {
  beforeEach(() => {
    vi.mocked(listGithubScopes).mockReset();
    vi.mocked(updateGithubScopes).mockReset();
    vi.mocked(listEmployers).mockReset();
    vi.mocked(listEmployers).mockResolvedValue(EMPLOYERS);
    vi.mocked(updateGithubScopes).mockResolvedValue([]);
  });

  it("asks to connect GitHub when no token is configured", () => {
    renderWithClient(<ScopeTable status={status({ configured: false })} />);

    expect(screen.getByText("Connect GitHub to list your repositories.")).toBeInTheDocument();
    expect(listGithubScopes).not.toHaveBeenCalled();
  });

  it("lists repositories with their badges", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/secret", is_private: true, is_new: true }),
      scope({ ref: "babbage/fork", is_fork: true }),
    ]);
    renderWithClient(<ScopeTable status={status()} />);

    expect(await screen.findByText("ada/secret")).toBeInTheDocument();
    expect(screen.getByText("Private repo")).toBeInTheDocument();
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByText("Fork")).toBeInTheDocument();
  });

  it("enables a public repository straight away without a disclosure", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope()]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", { name: "Sync ada/engine" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/engine", enabled: true }],
        false,
      );
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("requires the disclosure the first time a private repository is enabled", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ ref: "ada/secret", is_private: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", { name: "Sync ada/secret" }));

    expect(
      await screen.findByRole("dialog", { name: "Use a private repository?" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/file contents, diffs and your GitHub token/)).toBeInTheDocument();
    expect(updateGithubScopes).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "I understand — enable" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith([{ ref: "ada/secret", enabled: true }], true);
    });
  });

  it("does nothing when the disclosure is cancelled", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ ref: "ada/secret", is_private: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", { name: "Sync ada/secret" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(updateGithubScopes).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows only a short confirmation once the disclosure was acknowledged", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ ref: "ada/secret", is_private: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status({ acknowledged_at: "2026-10-01T00:00:00Z" })} />);

    await user.click(await screen.findByRole("checkbox", { name: "Sync ada/secret" }));

    expect(await screen.findByRole("dialog", { name: "Enable ada/secret?" })).toBeInTheDocument();
    expect(screen.queryByText(/file contents, diffs/)).not.toBeInTheDocument();
  });

  it("disables a repository without asking", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ enabled: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", { name: "Sync ada/engine" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/engine", enabled: false }],
        false,
      );
    });
  });

  it("changes the content level", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ enabled: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Content level for ada/engine" }),
      "metadata_only",
    );

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/engine", content_level: "metadata_only" }],
        false,
      );
    });
  });

  it("offers the employer mapping only after a repository has synced", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/unsynced" }),
      scope({ ref: "ada/synced", last_synced_at: "2026-10-02T00:00:00Z" }),
    ]);
    renderWithClient(<ScopeTable status={status()} />);

    expect(
      await screen.findByRole("combobox", { name: "Employer for ada/synced" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Employer for ada/unsynced" }),
    ).not.toBeInTheDocument();
  });

  it("maps a repository to an employer or to personal work", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/synced", last_synced_at: "2026-10-02T00:00:00Z" }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);
    const select = await screen.findByRole("combobox", { name: "Employer for ada/synced" });

    await screen.findByRole("option", { name: "Acme Corp (Mar 2021)" });
    await user.selectOptions(select, "Acme Corp (Mar 2021)");
    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenLastCalledWith(
        [{ ref: "ada/synced", employer_ref: { company: "Acme Corp", start_date: "Mar 2021" } }],
        false,
      );
    });
    await user.selectOptions(select, "Personal / open source");
    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenLastCalledWith(
        [{ ref: "ada/synced", employer_ref: { kind: "personal" } }],
        false,
      );
    });
  });

  it("applies a suggested employer with one click", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({
        ref: "ada/synced",
        last_synced_at: "2026-10-02T00:00:00Z",
        suggested_employer: { company: "Acme Corp", start_date: "Mar 2021", source: "suggested" },
      }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(
      await screen.findByRole("button", { name: /Suggested: Acme Corp \(Mar 2021\)/ }),
    );

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [
          {
            ref: "ada/synced",
            employer_ref: { company: "Acme Corp", start_date: "Mar 2021", source: "suggested" },
          },
        ],
        false,
      );
    });
  });

  it("offers a retry when the repositories cannot be loaded", async () => {
    vi.mocked(listGithubScopes).mockRejectedValueOnce(new Error("boom"));
    vi.mocked(listGithubScopes).mockResolvedValueOnce([scope()]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByText("ada/engine")).toBeInTheDocument();
  });
});

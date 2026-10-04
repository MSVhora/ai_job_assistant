"use client";

import { screen, waitFor, within } from "@testing-library/react";
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
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const EMPLOYERS = [
  {
    kind: "experience" as const,
    label: "Acme Corp (Mar 2021)",
    company: "Acme Corp",
    start_date: "Mar 2021",
  },
  { kind: "personal" as const, label: "Personal / open source", company: null, start_date: null },
];

const include = (ref: string) => ({ name: `Include ${ref}` });

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

  it("lists repositories with their badges and explains what selecting means", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/secret", is_private: true, is_new: true }),
      scope({ ref: "babbage/fork", is_fork: true }),
    ]);
    renderWithClient(<ScopeTable status={status()} />);

    expect(await screen.findByText("ada/secret")).toBeInTheDocument();
    expect(screen.getByText("Private repo")).toBeInTheDocument();
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByText("Fork")).toBeInTheDocument();
    expect(screen.getByText(/nothing is read from the rest/)).toBeInTheDocument();
    expect(screen.getByText("0 of 2 selected")).toBeInTheDocument();
  });

  it("changes nothing on the server until Save is pressed", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope()]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", include("ada/engine")));

    expect(screen.getByText("1 unsaved change")).toBeInTheDocument();
    expect(screen.getByText("Unsaved")).toBeInTheDocument();
    expect(updateGithubScopes).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/engine", enabled: true }],
        false,
      );
    });
    await waitFor(() => {
      expect(screen.queryByText("1 unsaved change")).not.toBeInTheDocument();
    });
  });

  it("discards unsaved edits without calling the server", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope()]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);
    const box = await screen.findByRole("checkbox", include("ada/engine"));

    await user.click(box);
    await user.click(screen.getByRole("button", { name: "Discard" }));

    expect(box).not.toBeChecked();
    expect(screen.queryByRole("region", { name: "Unsaved repository changes" })).toBeNull();
    expect(updateGithubScopes).not.toHaveBeenCalled();
  });

  it("drops an edit that is undone before saving", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope()]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);
    const box = await screen.findByRole("checkbox", include("ada/engine"));

    await user.click(box);
    await user.click(box);

    expect(screen.queryByText(/unsaved change/)).not.toBeInTheDocument();
  });

  it("selects and clears every repository, and saves them in one request", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "acme/api" }),
      scope({ ref: "acme/web" }),
      scope({ ref: "acme/old", enabled: true }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("button", { name: "Select all" }));
    expect(screen.getByText("3 of 3 selected")).toBeInTheDocument();
    expect(screen.getByText("2 unsaved changes")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledTimes(1);
    });
    expect(updateGithubScopes).toHaveBeenCalledWith(
      [
        { ref: "acme/api", enabled: true },
        { ref: "acme/web", enabled: true },
      ],
      false,
    );

    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(screen.getByText("0 of 3 selected")).toBeInTheDocument();
  });

  it("applies Select all only to the repositories matching the filter", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "acme/api" }),
      scope({ ref: "acme/web" }),
      scope({ ref: "ada/engine" }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.type(await screen.findByRole("searchbox", { name: "Filter repositories" }), "acme");
    expect(screen.queryByText("ada/engine")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Select all 2 shown" }));

    expect(screen.getByText("2 of 3 selected")).toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: "Filter repositories" }));
    expect(screen.getByRole("checkbox", include("ada/engine"))).not.toBeChecked();
  });

  it("says when the filter matches nothing", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope()]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.type(await screen.findByRole("searchbox", { name: "Filter repositories" }), "zzz");

    expect(screen.getByText("No repository matches “zzz”.")).toBeInTheDocument();
  });

  it("asks for the disclosure once, listing every private repository, when saving", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/secret", is_private: true }),
      scope({ ref: "ada/vault", is_private: true }),
      scope({ ref: "ada/open" }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("button", { name: "Select all" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    const dialog = await screen.findByRole("dialog", { name: "Use private repositories?" });
    expect(within(dialog).getByText(/ada\/secret, ada\/vault/)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/file contents, diffs and your GitHub token/),
    ).toBeInTheDocument();
    expect(updateGithubScopes).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: "I understand — save" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [
          { ref: "ada/secret", enabled: true },
          { ref: "ada/vault", enabled: true },
          { ref: "ada/open", enabled: true },
        ],
        true,
      );
    });
  });

  it("keeps the draft when the disclosure is cancelled", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ ref: "ada/secret", is_private: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", include("ada/secret")));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(updateGithubScopes).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("1 unsaved change")).toBeInTheDocument();
  });

  it("shows only a short confirmation once the disclosure was acknowledged", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ ref: "ada/secret", is_private: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status({ acknowledged_at: "2026-10-01T00:00:00Z" })} />);

    await user.click(await screen.findByRole("checkbox", include("ada/secret")));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("dialog", { name: "Enable ada/secret?" })).toBeInTheDocument();
    expect(screen.queryByText(/file contents, diffs/)).not.toBeInTheDocument();
  });

  it("does not ask for the disclosure when only disabling or changing a private repository", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/secret", is_private: true, enabled: true }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", include("ada/secret")));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/secret", enabled: false }],
        false,
      );
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("saves a content level change together with a selection", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ enabled: true })]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Content level for ada/engine" }),
      "metadata_only",
    );
    expect(updateGithubScopes).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

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

  it("maps a repository to an employer or to personal work, saved with the rest", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/synced", last_synced_at: "2026-10-02T00:00:00Z" }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);
    const select = await screen.findByRole("combobox", { name: "Employer for ada/synced" });

    await screen.findByRole("option", { name: "Acme Corp (Mar 2021)" });
    await user.selectOptions(select, "Acme Corp (Mar 2021)");
    await user.selectOptions(select, "Personal / open source");
    expect(updateGithubScopes).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/synced", employer_ref: { kind: "personal" } }],
        false,
      );
    });
  });

  it("applies a suggested employer to the draft with one click", async () => {
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
    await user.click(screen.getByRole("button", { name: "Save changes" }));

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

  it("keeps the draft and shows the error when saving fails", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope()]);
    vi.mocked(updateGithubScopes).mockRejectedValue(new Error("backend unavailable"));
    const user = userEvent.setup();
    renderWithClient(<ScopeTable status={status()} />);

    await user.click(await screen.findByRole("checkbox", include("ada/engine")));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("backend unavailable");
    expect(screen.getByText("1 unsaved change")).toBeInTheDocument();
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

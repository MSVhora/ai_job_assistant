import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listEmployers, listGithubScopes, updateGithubScopes } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { employerOption, PERSONAL_OPTION, scope } from "../evidence/fixtures";
import { RepositoryFilter } from "./RepositoryFilter";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  listEmployers: vi.fn(),
  listGithubScopes: vi.fn(),
  updateGithubScopes: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const EMPLOYERS = [employerOption("Acme Corp", { label: "Acme Corp (Mar 2021)" }), PERSONAL_OPTION];

describe("RepositoryFilter", () => {
  beforeEach(() => {
    vi.mocked(listEmployers).mockResolvedValue(EMPLOYERS);
    vi.mocked(updateGithubScopes).mockReset();
    vi.mocked(updateGithubScopes).mockResolvedValue([]);
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/engine", enabled: true }),
      scope({ ref: "ada/side", enabled: true, employer_ref: { kind: "personal", source: "user" } }),
      scope({ ref: "ada/ignored", enabled: false }),
    ]);
  });

  it("lists only repositories that are selected or synced, and reports the choice", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithClient(<RepositoryFilter value="" onChange={onChange} />);

    const select = await screen.findByRole("combobox", { name: "Repository" });
    await screen.findByRole("option", { name: "ada/engine — no employer set" });
    expect(screen.queryByRole("option", { name: /ada\/ignored/ })).not.toBeInTheDocument();
    await user.selectOptions(select, "ada/side");

    expect(onChange).toHaveBeenCalledWith("ada/side");
  });

  it("shows each repository's employer beside its name, and says when none is set", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "ada/engine", enabled: true }),
      scope({ ref: "ada/side", enabled: true, employer_ref: { kind: "personal", source: "user" } }),
      scope({
        ref: "ada/work",
        enabled: true,
        employer_ref: { company: "Samsung Research Institute", start_date: null, source: "scope" },
      }),
    ]);
    vi.mocked(listEmployers).mockResolvedValue([
      employerOption("Samsung", { aliases: ["Samsung", "Samsung Research Institute"] }),
      PERSONAL_OPTION,
    ]);
    renderWithClient(<RepositoryFilter value="" onChange={vi.fn()} />);

    const options = await screen.findAllByRole("option");

    expect(options.map((option) => option.textContent)).toEqual([
      "All repositories",
      "ada/engine — no employer set",
      "ada/side — Personal / open source",
      "ada/work — Samsung",
    ]);
  });

  it("shows no employer bar while all repositories are shown", async () => {
    renderWithClient(<RepositoryFilter value="" onChange={vi.fn()} />);

    await screen.findByRole("option", { name: "ada/engine — no employer set" });

    expect(screen.queryByText(/Employer for/)).not.toBeInTheDocument();
  });

  it("maps the chosen repository to an employer for all its achievements", async () => {
    const user = userEvent.setup();
    renderWithClient(<RepositoryFilter value="ada/engine" onChange={vi.fn()} />);
    await screen.findByRole("option", { name: "Acme Corp (Mar 2021)" });

    expect(screen.getByRole("button", { name: "Apply to this repository" })).toBeDisabled();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Employer for ada/engine" }),
      "Acme Corp (Mar 2021)",
    );
    await user.click(screen.getByRole("button", { name: "Apply to this repository" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/engine", employer_ref: { company: "Acme Corp" } }],
        false,
      );
    });
    expect(screen.getByText(/keep it/)).toBeInTheDocument();
  });

  it("starts from the repository's current employer and can unmap it", async () => {
    const user = userEvent.setup();
    renderWithClient(<RepositoryFilter value="ada/side" onChange={vi.fn()} />);
    const select = await screen.findByRole("combobox", { name: "Employer for ada/side" });
    await screen.findByRole("option", { name: "Personal / open source" });

    expect(select).toHaveValue("personal");
    await user.selectOptions(select, "");
    await user.click(screen.getByRole("button", { name: "Apply to this repository" }));

    await waitFor(() => {
      expect(updateGithubScopes).toHaveBeenCalledWith(
        [{ ref: "ada/side", employer_ref: null }],
        false,
      );
    });
  });

  it("renders nothing when no repository has been selected or synced yet", async () => {
    vi.mocked(listGithubScopes).mockResolvedValue([scope({ ref: "ada/ignored", enabled: false })]);
    renderWithClient(<RepositoryFilter value="" onChange={vi.fn()} />);

    await waitFor(() => {
      expect(listGithubScopes).toHaveBeenCalled();
    });
    expect(screen.queryByRole("combobox", { name: "Repository" })).not.toBeInTheDocument();
  });

  it("lists only the allowed repositories when an employer narrows the choice", async () => {
    renderWithClient(
      <RepositoryFilter value="" onChange={vi.fn()} allowed={new Set(["ada/side"])} />,
    );

    await screen.findByRole("option", { name: /ada\/side/ });
    expect(screen.queryByRole("option", { name: /ada\/engine/ })).not.toBeInTheDocument();
  });
});

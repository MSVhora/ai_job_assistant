import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { editAchievement, listEmployers, listGithubScopes } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { employerOption, PERSONAL_OPTION, scope } from "../evidence/fixtures";
import { achievement } from "./fixtures";
import { EmployerEditor } from "./EmployerEditor";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  editAchievement: vi.fn(),
  listEmployers: vi.fn(),
  listGithubScopes: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const EMPLOYERS = [employerOption("Acme Corp", { label: "Acme Corp (Mar 2021)" }), PERSONAL_OPTION];

describe("EmployerEditor", () => {
  beforeEach(() => {
    vi.mocked(editAchievement).mockReset();
    vi.mocked(editAchievement).mockResolvedValue(achievement());
    vi.mocked(listEmployers).mockResolvedValue(EMPLOYERS);
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({
        ref: "ada/engine",
        employer_ref: { company: "Acme Corp", start_date: "Mar 2021", source: "user" },
      }),
    ]);
  });

  it("defaults to following the repository and names its employer", async () => {
    renderWithClient(<EmployerEditor achievement={achievement({ employer_ref: null })} />);

    const select = await screen.findByRole("combobox", { name: "Employer" });

    await screen.findByRole("option", { name: "Same as repository (Acme Corp)" });
    expect(select).toHaveValue("");
    expect(screen.getByRole("button", { name: "Save employer" })).toBeDisabled();
  });

  it("saves an individual employer choice", async () => {
    const user = userEvent.setup();
    renderWithClient(<EmployerEditor achievement={achievement()} />);
    await screen.findByRole("option", { name: "Personal / open source" });

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Employer" }),
      "Personal / open source",
    );
    await user.click(screen.getByRole("button", { name: "Save employer" }));

    await waitFor(() => {
      expect(editAchievement).toHaveBeenCalledWith("a1", { employer_ref: { kind: "personal" } });
    });
  });

  it("saves a company choice with its start date", async () => {
    const user = userEvent.setup();
    renderWithClient(<EmployerEditor achievement={achievement()} />);
    await screen.findByRole("option", { name: "Acme Corp (Mar 2021)" });

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Employer" }),
      "Acme Corp (Mar 2021)",
    );
    await user.click(screen.getByRole("button", { name: "Save employer" }));

    await waitFor(() => {
      expect(editAchievement).toHaveBeenCalledWith("a1", {
        employer_ref: { company: "Acme Corp" },
      });
    });
  });

  it("shows your own choice as selected and clears it by following the repository again", async () => {
    const user = userEvent.setup();
    renderWithClient(
      <EmployerEditor
        achievement={achievement({ employer_ref: { kind: "personal", source: "user" } })}
      />,
    );
    const select = await screen.findByRole("combobox", { name: "Employer" });
    await screen.findByRole("option", { name: "Personal / open source" });

    expect(select).toHaveValue("personal");
    await user.selectOptions(select, "");
    await user.click(screen.getByRole("button", { name: "Save employer" }));

    await waitFor(() => {
      expect(editAchievement).toHaveBeenCalledWith("a1", { employer_ref: null });
    });
  });

  it("offers no repository to follow when the achievement has no source", async () => {
    renderWithClient(<EmployerEditor achievement={achievement({ project_key: null })} />);

    expect(await screen.findByRole("option", { name: "Not set" })).toBeInTheDocument();
  });
});

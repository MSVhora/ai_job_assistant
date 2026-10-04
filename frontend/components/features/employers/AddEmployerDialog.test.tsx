import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addProfileExperience, listEmployers, listProfiles } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { employerOption, PERSONAL_OPTION } from "../evidence/fixtures";
import { AddEmployerDialog } from "./AddEmployerDialog";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  addProfileExperience: vi.fn(),
  listEmployers: vi.fn(),
  listProfiles: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const profile = (id: string, name: string, updated: string) => ({
  profile_id: id,
  name,
  source_resume_filename: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: updated,
});

describe("AddEmployerDialog", () => {
  beforeEach(() => {
    vi.mocked(addProfileExperience).mockReset();
    vi.mocked(addProfileExperience).mockResolvedValue({} as never);
    vi.mocked(listEmployers).mockResolvedValue([PERSONAL_OPTION]);
    vi.mocked(listProfiles).mockResolvedValue([
      profile("p1", "Backend track", "2026-10-01T00:00:00Z"),
    ]);
  });

  it("needs a company name", async () => {
    const user = userEvent.setup();
    renderWithClient(<AddEmployerDialog open onClose={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "Add employer" }));

    expect(await screen.findByText("Enter the company name")).toBeInTheDocument();
    expect(addProfileExperience).not.toHaveBeenCalled();
  });

  it("adds the role to the only profile, sending just the fields that were filled in", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithClient(<AddEmployerDialog open onClose={onClose} />);
    await screen.findByText(/the profile “Backend track”/);

    await user.type(screen.getByLabelText("Company"), "  Zeta Labs ");
    await user.type(screen.getByLabelText("Start (optional)"), "Jan 2024");
    await user.click(screen.getByRole("button", { name: "Add employer" }));

    await waitFor(() => {
      expect(addProfileExperience).toHaveBeenCalledWith("p1", {
        company: "Zeta Labs",
        is_current: false,
        start_date: "Jan 2024",
      });
    });
    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("offers a profile choice only when there are several, defaulting to the newest", async () => {
    vi.mocked(listProfiles).mockResolvedValue([
      profile("old", "Old track", "2025-01-01T00:00:00Z"),
      profile("new", "New track", "2026-09-01T00:00:00Z"),
    ]);
    const user = userEvent.setup();
    renderWithClient(<AddEmployerDialog open onClose={vi.fn()} />);

    const select = await screen.findByRole("combobox", { name: "Add to profile" });
    expect(select).toHaveValue("new");
    await user.type(screen.getByLabelText("Company"), "Zeta Labs");
    await user.selectOptions(select, "old");
    await user.click(screen.getByRole("button", { name: "Add employer" }));

    await waitFor(() => {
      expect(addProfileExperience).toHaveBeenCalledWith(
        "old",
        expect.objectContaining({ company: "Zeta Labs" }),
      );
    });
  });

  it("drops the end date for a current job", async () => {
    const user = userEvent.setup();
    renderWithClient(<AddEmployerDialog open onClose={vi.fn()} />);
    await screen.findByText(/the profile “Backend track”/);

    await user.type(screen.getByLabelText("Company"), "Zeta Labs");
    await user.type(screen.getByLabelText("End (optional)"), "Dec 2024");
    await user.click(screen.getByRole("checkbox", { name: "I work here now" }));
    await user.click(screen.getByRole("button", { name: "Add employer" }));

    await waitFor(() => {
      expect(addProfileExperience).toHaveBeenCalledWith("p1", {
        company: "Zeta Labs",
        is_current: true,
      });
    });
  });

  it("hands the new employer's key back so the caller can select it", async () => {
    const onAdded = vi.fn();
    vi.mocked(listEmployers).mockResolvedValue([
      employerOption("Zeta Labs", { key: "zeta labs" }),
      PERSONAL_OPTION,
    ]);
    const user = userEvent.setup();
    renderWithClient(<AddEmployerDialog open onClose={vi.fn()} onAdded={onAdded} />);
    await screen.findByText(/the profile “Backend track”/);

    await user.type(screen.getByLabelText("Company"), "Zeta Labs");
    await user.click(screen.getByRole("button", { name: "Add employer" }));

    await waitFor(() => {
      expect(onAdded).toHaveBeenCalledWith("zeta labs");
    });
  });

  it("shows the server's reason and keeps the dialog open", async () => {
    vi.mocked(addProfileExperience).mockRejectedValue(
      new Error("this role is already in the profile"),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithClient(<AddEmployerDialog open onClose={onClose} />);
    await screen.findByText(/the profile “Backend track”/);

    await user.type(screen.getByLabelText("Company"), "Zeta Labs");
    await user.click(screen.getByRole("button", { name: "Add employer" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already in the profile");
    expect(onClose).not.toHaveBeenCalled();
  });
});

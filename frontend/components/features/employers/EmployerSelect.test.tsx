import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listEmployers, listProfiles } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { employerOption, PERSONAL_OPTION } from "../evidence/fixtures";
import { EmployerSelect } from "./EmployerSelect";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  addProfileExperience: vi.fn(),
  listEmployers: vi.fn(),
  listProfiles: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const OPTIONS = [
  employerOption("Acme Corp", { label: "Acme Corp · 2020 – 2022 · 2 roles" }),
  PERSONAL_OPTION,
];

describe("EmployerSelect", () => {
  beforeEach(() => {
    vi.mocked(listEmployers).mockResolvedValue(OPTIONS);
    vi.mocked(listProfiles).mockResolvedValue([]);
  });

  it("offers none, one choice per employer and a way to add one", () => {
    renderWithClient(
      <EmployerSelect
        ariaLabel="Employer"
        value=""
        options={OPTIONS}
        noneLabel="Not mapped"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Not mapped",
      "Acme Corp · 2020 – 2022 · 2 roles",
      "Personal / open source",
      "+ Add an employer…",
    ]);
  });

  it("reports the chosen employer's key", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithClient(
      <EmployerSelect
        ariaLabel="Employer"
        value=""
        options={OPTIONS}
        noneLabel="Not mapped"
        onChange={onChange}
      />,
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "Employer" }), "personal");

    expect(onChange).toHaveBeenCalledWith("personal");
  });

  it("opens the add dialog instead of choosing when add is picked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithClient(
      <EmployerSelect
        ariaLabel="Employer"
        value=""
        options={OPTIONS}
        noneLabel="Not mapped"
        onChange={onChange}
      />,
    );

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Employer" }),
      "+ Add an employer…",
    );

    expect(await screen.findByRole("dialog", { name: "Add an employer" })).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});

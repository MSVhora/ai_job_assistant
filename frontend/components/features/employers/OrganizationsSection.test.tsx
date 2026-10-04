import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listGithubScopes, listOwners, setOwnerEmployer, type OwnerSummary } from "@/lib/api";

import { employerOption, PERSONAL_OPTION, scope } from "../evidence/fixtures";
import { renderWithClient } from "../test-utils";
import { OrganizationsSection } from "./OrganizationsSection";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  listGithubScopes: vi.fn(),
  listOwners: vi.fn(),
  setOwnerEmployer: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const ACME = employerOption("Acme Corp");
const OPTIONS = [ACME, PERSONAL_OPTION];

function owner(overrides: Partial<OwnerSummary> = {}): OwnerSummary {
  return {
    owner: "acme-org",
    repos: 3,
    selected: 1,
    explicit: 1,
    employer: null,
    personal_account: false,
    ...overrides,
  };
}

describe("OrganizationsSection", () => {
  beforeEach(() => {
    vi.mocked(listOwners).mockReset();
    vi.mocked(setOwnerEmployer).mockReset();
    vi.mocked(listOwners).mockResolvedValue([
      owner(),
      owner({ owner: "ada", repos: 2, selected: 0, personal_account: true }),
    ]);
    vi.mocked(listGithubScopes).mockResolvedValue([
      scope({ ref: "acme-org/api" }),
      scope({ ref: "Acme-Org/web", enabled: true }),
      scope({ ref: "acme-org/own", employer_ref: { kind: "personal", source: "user" } }),
    ]);
    vi.mocked(setOwnerEmployer).mockResolvedValue([]);
  });

  it("lists owners with how many repositories are selected and flags your own account", async () => {
    renderWithClient(<OrganizationsSection options={OPTIONS} />);

    expect(await screen.findByText("1 of 3 selected")).toBeInTheDocument();
    expect(screen.getByText("Your account")).toBeInTheDocument();
  });

  it("previews who changes, then applies the employer to the organization", async () => {
    const user = userEvent.setup();
    renderWithClient(<OrganizationsSection options={OPTIONS} />);

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Employer for organization acme-org" }),
      "acme corp",
    );

    expect(screen.getByText(/2 repositories change, selected or not; 1 keeps/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Apply employer to acme-org" }));

    await waitFor(() => {
      expect(setOwnerEmployer).toHaveBeenCalledWith("acme-org", { company: "Acme Corp" });
    });
  });

  it("shows nothing when there are no repositories yet", async () => {
    vi.mocked(listOwners).mockResolvedValue([]);
    renderWithClient(<OrganizationsSection options={OPTIONS} />);

    await waitFor(() => {
      expect(listOwners).toHaveBeenCalled();
    });
    expect(screen.queryByRole("region", { name: "Organizations" })).not.toBeInTheDocument();
  });
});

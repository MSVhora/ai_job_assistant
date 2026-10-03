"use client";

import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getChunkSummary,
  getEvidenceStatus,
  listEmployers,
  listGithubScopes,
  listNotes,
  listProfiles,
  listSyncs,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { status } from "./fixtures";
import { EvidencePageClient } from "./EvidencePageClient";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getChunkSummary: vi.fn(),
  getEvidenceStatus: vi.fn(),
  listEmployers: vi.fn(),
  listGithubScopes: vi.fn(),
  listNotes: vi.fn(),
  listProfiles: vi.fn(),
  listSyncs: vi.fn(),
}));

describe("EvidencePageClient", () => {
  beforeEach(() => {
    for (const fn of [
      getChunkSummary,
      getEvidenceStatus,
      listEmployers,
      listGithubScopes,
      listNotes,
      listProfiles,
      listSyncs,
    ]) {
      vi.mocked(fn).mockReset();
    }
    vi.mocked(listNotes).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(listProfiles).mockResolvedValue([]);
    vi.mocked(listSyncs).mockResolvedValue([]);
    vi.mocked(listEmployers).mockResolvedValue([]);
    vi.mocked(listGithubScopes).mockResolvedValue([]);
    vi.mocked(getChunkSummary).mockResolvedValue({
      chunks: 0,
      tokens: 0,
      private_chunks: 0,
      private_share: 0,
      embedded: 0,
      pending_embedding: 0,
      by_kind: {},
    });
  });

  it("shows a loading placeholder, then every section", async () => {
    vi.mocked(getEvidenceStatus).mockResolvedValue(status());
    renderWithClient(<EvidencePageClient />);

    expect(await screen.findByRole("heading", { name: "GitHub connection" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Repositories" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sync" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Notes, links and resume" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Achievements" })).toBeInTheDocument();
    expect(screen.getByText(/Connected as/)).toHaveTextContent("ada");
  });

  it("tells you how to configure GitHub while keeping notes available", async () => {
    vi.mocked(getEvidenceStatus).mockResolvedValue(status({ configured: false, login: null }));
    renderWithClient(<EvidencePageClient />);

    expect(await screen.findByText("Token missing")).toBeInTheDocument();
    expect(screen.getByText(/GITHUB_TOKEN/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Setup" })).toHaveAttribute("href", "/setup");
    expect(screen.getByRole("button", { name: "Add note" })).toBeInTheDocument();
  });

  it("warns about repositories without an employer mapping", async () => {
    vi.mocked(getEvidenceStatus).mockResolvedValue(status({ scopes_unmapped: 2 }));
    renderWithClient(<EvidencePageClient />);

    expect(
      await screen.findByText(/2 synced repositories are not mapped to an employer/),
    ).toBeInTheDocument();
  });

  it("offers a retry when the status cannot be loaded", async () => {
    vi.mocked(getEvidenceStatus).mockRejectedValueOnce(new Error("down"));
    vi.mocked(getEvidenceStatus).mockResolvedValueOnce(status());
    const user = userEvent.setup();
    renderWithClient(<EvidencePageClient />);

    await user.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("heading", { name: "GitHub connection" })).toBeInTheDocument();
  });
});

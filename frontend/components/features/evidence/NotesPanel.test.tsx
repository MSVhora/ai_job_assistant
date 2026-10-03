"use client";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createLink,
  createNote,
  deleteNote,
  ingestResume,
  listNotes,
  listProfiles,
  updateNote,
  type EvidenceItem,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { NotesPanel } from "./NotesPanel";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  createLink: vi.fn(),
  createNote: vi.fn(),
  deleteNote: vi.fn(),
  ingestResume: vi.fn(),
  listNotes: vi.fn(),
  listProfiles: vi.fn(),
  updateNote: vi.fn(),
}));

function note(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: "n1",
    kind: "note",
    external_id: "x",
    project_key: "note:payments",
    title: "Payments",
    body: "Moved 40 services to the ledger.",
    url: null,
    occurred_at: null,
    authored_by_user: true,
    status: "kept",
    filter_reason: null,
    is_private: false,
    meta: {},
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:00:00Z",
    ...overrides,
  };
}

describe("NotesPanel", () => {
  beforeEach(() => {
    for (const fn of [
      createLink,
      createNote,
      deleteNote,
      ingestResume,
      listNotes,
      listProfiles,
      updateNote,
    ]) {
      vi.mocked(fn).mockReset();
    }
    vi.mocked(listNotes).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(listProfiles).mockResolvedValue([
      {
        profile_id: "p1",
        name: "Backend",
        source_resume_filename: null,
        created_at: "",
        updated_at: "",
      },
    ]);
  });

  it("shows an empty state and adds a note", async () => {
    vi.mocked(createNote).mockResolvedValue(note());
    const user = userEvent.setup();
    renderWithClient(<NotesPanel />);
    expect(await screen.findByText("No notes yet.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Note title (optional)"), "Payments");
    await user.type(screen.getByLabelText("What did you do?"), "Moved 40 services.");
    await user.click(screen.getByRole("button", { name: "Add note" }));

    await waitFor(() => {
      expect(createNote).toHaveBeenCalledWith({ title: "Payments", body: "Moved 40 services." });
    });
    expect(screen.getByLabelText("What did you do?")).toHaveValue("");
  });

  it("sends a null title when none was typed and blocks an empty body", async () => {
    vi.mocked(createNote).mockResolvedValue(note());
    const user = userEvent.setup();
    renderWithClient(<NotesPanel />);
    await screen.findByText("No notes yet.");

    expect(screen.getByRole("button", { name: "Add note" })).toBeDisabled();
    await user.type(screen.getByLabelText("What did you do?"), "Just a body");
    await user.click(screen.getByRole("button", { name: "Add note" }));

    await waitFor(() => {
      expect(createNote).toHaveBeenCalledWith({ title: null, body: "Just a body" });
    });
  });

  it("edits and deletes an existing note", async () => {
    vi.mocked(listNotes).mockResolvedValue({ items: [note()], total: 1 });
    vi.mocked(updateNote).mockResolvedValue(note({ body: "Rewritten" }));
    vi.mocked(deleteNote).mockResolvedValue();
    const user = userEvent.setup();
    renderWithClient(<NotesPanel />);

    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const editor = screen.getByLabelText("Edit note");
    await user.clear(editor);
    await user.type(editor, "Rewritten");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(updateNote).toHaveBeenCalledWith("n1", { body: "Rewritten" });
    });

    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(deleteNote).toHaveBeenCalledWith("n1");
    });
  });

  it("saves a link with only the fields that were filled in", async () => {
    vi.mocked(createLink).mockResolvedValue(note({ kind: "link" }));
    const user = userEvent.setup();
    renderWithClient(<NotesPanel />);
    await screen.findByText("No notes yet.");

    await user.type(screen.getByLabelText("Link URL"), "https://example.com/talk");
    await user.click(screen.getByRole("button", { name: "Save link" }));

    await waitFor(() => {
      expect(createLink).toHaveBeenCalledWith({ url: "https://example.com/talk" });
    });
  });

  it("includes the title and pasted text when given", async () => {
    vi.mocked(createLink).mockResolvedValue(note({ kind: "link" }));
    const user = userEvent.setup();
    renderWithClient(<NotesPanel />);
    await screen.findByText("No notes yet.");

    await user.type(screen.getByLabelText("Link URL"), "https://example.com/talk");
    await user.type(screen.getByLabelText("Link title (optional)"), "My talk");
    await user.type(screen.getByLabelText("Pasted text (optional)"), "I presented the loader");
    await user.click(screen.getByRole("button", { name: "Save link" }));

    await waitFor(() => {
      expect(createLink).toHaveBeenCalledWith({
        url: "https://example.com/talk",
        title: "My talk",
        text: "I presented the loader",
      });
    });
  });

  it("ingests the chosen profile's resume entries", async () => {
    vi.mocked(ingestResume).mockResolvedValue({ created: 3, unchanged: 0, excluded: 0 });
    const user = userEvent.setup();
    renderWithClient(<NotesPanel />);

    await screen.findByRole("option", { name: "Backend" });
    await user.click(screen.getByRole("button", { name: "Ingest resume entries" }));

    await waitFor(() => {
      expect(ingestResume).toHaveBeenCalledWith("p1");
    });
  });

  it("asks you to create a profile first when there is none", async () => {
    vi.mocked(listProfiles).mockResolvedValue([]);
    renderWithClient(<NotesPanel />);

    expect(await screen.findByText(/Create a profile from your resume first/)).toBeInTheDocument();
  });
});

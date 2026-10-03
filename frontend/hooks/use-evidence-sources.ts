"use client";

import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createLink,
  createNote,
  deleteNote,
  getChunkSummary,
  getEvidenceItem,
  ingestResume,
  listNotes,
  updateNote,
  type LinkCreate,
  type NoteCreate,
  type NoteUpdate,
} from "@/lib/api";

export function useNotes() {
  return useQuery({ queryKey: ["evidence-notes"], queryFn: listNotes });
}

export function useChunkSummary() {
  return useQuery({ queryKey: ["evidence-chunks"], queryFn: getChunkSummary });
}

export function useEvidenceItem(itemId: string | null) {
  return useQuery({
    queryKey: ["evidence-item", itemId],
    queryFn: itemId !== null ? () => getEvidenceItem(itemId) : skipToken,
    staleTime: 60_000,
  });
}

function useRefreshEvidence() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["evidence-notes"] });
    void queryClient.invalidateQueries({ queryKey: ["evidence-chunks"] });
  };
}

export function useCreateNote() {
  const refresh = useRefreshEvidence();
  return useMutation({
    mutationFn: (payload: NoteCreate) => createNote(payload),
    onSuccess: refresh,
  });
}

export function useUpdateNote() {
  const refresh = useRefreshEvidence();
  return useMutation({
    mutationFn: ({ noteId, payload }: { noteId: string; payload: NoteUpdate }) =>
      updateNote(noteId, payload),
    onSuccess: refresh,
  });
}

export function useDeleteNote() {
  const refresh = useRefreshEvidence();
  return useMutation({ mutationFn: (noteId: string) => deleteNote(noteId), onSuccess: refresh });
}

export function useCreateLink() {
  const refresh = useRefreshEvidence();
  return useMutation({
    mutationFn: (payload: LinkCreate) => createLink(payload),
    onSuccess: refresh,
  });
}

export function useIngestResume() {
  const refresh = useRefreshEvidence();
  return useMutation({
    mutationFn: (profileId: string) => ingestResume(profileId),
    onSuccess: refresh,
  });
}

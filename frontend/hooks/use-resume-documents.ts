"use client";

import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addResumeComment,
  applyResumeComments,
  approveResumeBulletAnyway,
  createResumeDocument,
  deleteResumeComment,
  deleteResumeDocument,
  fitResumeDocument,
  getResumeConflicts,
  getResumeDocument,
  includeRoleAnyway,
  listResumeDocuments,
  pinResumeBullet,
  regenerateResumeDocument,
  removeResumeBullet,
  resolveResumeConflict,
  updateResumeTemplate,
  writeAchievementBullet,
  type CommentCreate,
  type ResumeDocument,
  type ResumeDocumentCreate,
  type ResumeTemplate,
} from "@/lib/api";

const DOCUMENT_KEY = "resume-document";
const LIST_KEY = "resume-documents";
const CONFLICTS_KEY = "resume-conflicts";

export function useResumeDocuments(profileId: string | null) {
  return useQuery({
    queryKey: [LIST_KEY, profileId],
    queryFn: () => listResumeDocuments({ ...(profileId === null ? {} : { profileId }), limit: 50 }),
  });
}

export function useResumeDocument(id: string | null) {
  return useQuery({
    queryKey: [DOCUMENT_KEY, id],
    queryFn: id !== null ? () => getResumeDocument(id) : skipToken,
  });
}

export function useResumeConflicts(id: string | null, version: number | undefined) {
  return useQuery({
    queryKey: [CONFLICTS_KEY, id, version],
    queryFn: id !== null ? () => getResumeConflicts(id) : skipToken,
  });
}

export function useCreateResumeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ResumeDocumentCreate) => createResumeDocument(payload),
    onSuccess: (document) => {
      queryClient.setQueryData([DOCUMENT_KEY, document.id], document);
      void queryClient.invalidateQueries({ queryKey: [LIST_KEY] });
    },
  });
}

export function useDeleteResumeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteResumeDocument(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [LIST_KEY] }),
  });
}

/** Every mutation answers with the whole updated document, so the cache is replaced, not refetched. */
function useDocumentAction<Variables>(
  id: string,
  action: (id: string, variables: Variables) => Promise<ResumeDocument>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: Variables) => action(id, variables),
    onSuccess: (document) => {
      queryClient.setQueryData([DOCUMENT_KEY, id], document);
      void queryClient.invalidateQueries({ queryKey: [LIST_KEY] });
    },
  });
}

export function useRefit(id: string) {
  return useDocumentAction<undefined>(id, (docId) => fitResumeDocument(docId));
}

export function useRegenerate(id: string) {
  return useDocumentAction<string | undefined>(id, regenerateResumeDocument);
}

export function useChangeTemplate(id: string) {
  return useDocumentAction<ResumeTemplate>(id, updateResumeTemplate);
}

export function usePinBullet(id: string) {
  return useDocumentAction<{ bulletId: string; pinned: boolean }>(
    id,
    (docId, { bulletId, pinned }) => pinResumeBullet(docId, bulletId, pinned),
  );
}

export function useRemoveBullet(id: string) {
  return useDocumentAction<string>(id, removeResumeBullet);
}

export function useApproveBullet(id: string) {
  return useDocumentAction<string>(id, approveResumeBulletAnyway);
}

export function useIncludeRole(id: string) {
  return useDocumentAction<string>(id, includeRoleAnyway);
}

export function useWriteAchievement(id: string) {
  return useDocumentAction<string>(id, writeAchievementBullet);
}

export function useAddComment(id: string) {
  return useDocumentAction<CommentCreate>(id, addResumeComment);
}

export function useDeleteComment(id: string) {
  return useDocumentAction<string>(id, deleteResumeComment);
}

export function useApplyComments(id: string) {
  return useDocumentAction<undefined>(id, (docId) => applyResumeComments(docId));
}

export function useResolveConflict(id: string) {
  return useDocumentAction<{ key: string; action: "keep_as_is" | "reopen" }>(
    id,
    (docId, { key, action }) => resolveResumeConflict(docId, key, action),
  );
}

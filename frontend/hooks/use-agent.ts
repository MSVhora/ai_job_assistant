"use client";

import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createAgentSession,
  deleteAgentSession,
  getAgentSession,
  listAgentSessions,
  sendAgentMessage,
  type AgentGrounding,
  type AgentMessage,
  type AgentSession,
  type AgentSessionCreate,
} from "@/lib/api";

const SESSION_KEY = "agent-session";
const LIST_KEY = "agent-sessions";

export function useAgentSessions() {
  return useQuery({ queryKey: [LIST_KEY], queryFn: () => listAgentSessions() });
}

export function useAgentSession(id: string | null) {
  return useQuery({
    queryKey: [SESSION_KEY, id],
    queryFn: id !== null ? () => getAgentSession(id) : skipToken,
  });
}

export function useCreateAgentSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AgentSessionCreate) => createAgentSession(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [LIST_KEY] }),
  });
}

export function useDeleteAgentSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAgentSession(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [LIST_KEY] }),
  });
}

const EMPTY_GROUNDING: AgentGrounding = {
  status: "not_applicable",
  flagged_sentences: [],
  gaps: [],
  repaired: false,
  used_private: false,
  judge_unavailable: false,
  no_evidence: false,
  error: false,
};

function pendingMessage(sessionId: string, content: string): AgentMessage {
  return {
    id: `pending-${String(Date.now())}`,
    session_id: sessionId,
    role: "user",
    content,
    citations: [],
    grounding: EMPTY_GROUNDING,
    created_at: new Date().toISOString(),
  };
}

/** Shows the question at once and takes it back out if the request fails. */
export function useSendMessage(sessionId: string) {
  const queryClient = useQueryClient();
  const key = [SESSION_KEY, sessionId];
  return useMutation({
    mutationFn: (content: string) => sendAgentMessage(sessionId, content),
    onMutate: async (content) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<AgentSession>(key);
      if (previous !== undefined) {
        queryClient.setQueryData<AgentSession>(key, {
          ...previous,
          messages: [...previous.messages, pendingMessage(sessionId, content)],
        });
      }
      return { previous };
    },
    onError: (_error, _content, context) => {
      if (context?.previous !== undefined) queryClient.setQueryData(key, context.previous);
    },
    onSuccess: (turn, _content, context) => {
      const base = context.previous;
      if (base !== undefined) {
        queryClient.setQueryData<AgentSession>(key, {
          ...base,
          messages: [...base.messages, turn.user_message, turn.assistant_message],
        });
      }
      void queryClient.invalidateQueries({ queryKey: [LIST_KEY] });
    },
  });
}

"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { useSendMessage } from "@/hooks/use-agent";
import { createAgentSession, sendAgentMessage, type AgentSession } from "@/lib/api";

/**
 * Sends a question to the open conversation, or starts one with it. A conversation is only
 * created when the first question is sent, so an empty "New chat" never clutters the history.
 */
export function useChatSend(
  sessionId: string | null,
  profileId: string | null,
  onStarted: (sessionId: string) => void,
) {
  const queryClient = useQueryClient();
  const existing = useSendMessage(sessionId ?? "");
  const created = useRef<string | null>(null);

  const start = useMutation({
    mutationFn: async (question: string) => {
      if (profileId === null) throw new Error("Choose a profile first.");
      created.current ??= (await createAgentSession({ profile_id: profileId })).id;
      const turn = await sendAgentMessage(created.current, question);
      return { id: created.current, turn };
    },
    onSuccess: ({ id, turn }) => {
      const seeded: AgentSession = {
        id,
        profile_id: profileId ?? "",
        match_id: null,
        title: turn.user_message.content.slice(0, 60),
        style_notes: null,
        summary: null,
        job: null,
        messages: [turn.user_message, turn.assistant_message],
        created_at: turn.user_message.created_at,
        updated_at: turn.assistant_message.created_at,
      };
      queryClient.setQueryData(["agent-session", id], seeded);
      void queryClient.invalidateQueries({ queryKey: ["agent-sessions"] });
      created.current = null;
      onStarted(id);
    },
  });

  const active = sessionId === null ? start : existing;
  return {
    send: (question: string, onSent: () => void) => {
      active.mutate(question, { onSuccess: onSent });
    },
    isPending: active.isPending,
    error: active.isError ? active.error.message : null,
    pendingQuestion: sessionId === null && start.isPending ? start.variables : null,
  };
}

"use client";

import { useState } from "react";

import { useAgentSession } from "@/hooks/use-agent";
import { useChatSend } from "@/hooks/use-chat-send";
import { ApiError, type AgentCitation, type AgentMessage } from "@/lib/api";

import { ChatInput } from "./ChatInput";
import { ChatThread } from "./ChatThread";
import { useChat } from "./ChatProvider";
import { CitationPanel } from "./CitationPanel";
import { StarterQuestions } from "./StarterQuestions";

function pending(question: string): AgentMessage {
  return {
    id: "pending",
    session_id: "",
    role: "user",
    content: question,
    citations: [],
    grounding: {
      status: "not_applicable",
      flagged_sentences: [],
      gaps: [],
      repaired: false,
      used_private: false,
      judge_unavailable: false,
      no_evidence: false,
      error: false,
    },
    created_at: new Date().toISOString(),
  };
}

export function ChatConversation({ sessionId }: { sessionId: string | null }) {
  const { profileId, setSessionId } = useChat();
  const session = useAgentSession(sessionId);
  const chat = useChatSend(sessionId, profileId, setSessionId);
  const [draft, setDraft] = useState("");
  const [citation, setCitation] = useState<AgentCitation | null>(null);

  const ask = (question: string) => {
    chat.send(question, () => {
      setDraft((current) => (current === question ? "" : current));
    });
  };

  if (sessionId !== null && session.isPending) {
    return (
      <div
        role="status"
        aria-label="Loading conversation"
        className="h-40 animate-pulse rounded-2xl bg-gray-100"
      />
    );
  }
  if (sessionId !== null && session.isError) {
    const missing = session.error instanceof ApiError && session.error.status === 404;
    return (
      <div
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
      >
        {missing ? "This conversation was not found." : session.error.message}
        <button
          type="button"
          onClick={() => {
            if (missing) setSessionId(null);
            else void session.refetch();
          }}
          className="ml-3 rounded-full border border-red-300 px-3 py-1 text-xs font-semibold hover:bg-red-100"
        >
          {missing ? "Start a new chat" : "Retry"}
        </button>
      </div>
    );
  }

  const stored = session.data?.messages ?? [];
  const messages =
    chat.pendingQuestion === null ? stored : [...stored, pending(chat.pendingQuestion)];
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {messages.length === 0 ? (
          <StarterQuestions disabled={chat.isPending} onPick={setDraft} />
        ) : (
          <ChatThread
            messages={messages}
            busy={chat.isPending}
            onOpenCitation={setCitation}
            onReask={ask}
          />
        )}
      </div>
      <ChatInput
        value={draft}
        onChange={setDraft}
        onSend={() => {
          ask(draft.trim());
        }}
        pending={chat.isPending}
        error={chat.error}
      />
      <CitationPanel
        citation={citation}
        onClose={() => {
          setCitation(null);
        }}
      />
    </div>
  );
}

"use client";

import { useAgentSessions, useDeleteAgentSession } from "@/hooks/use-agent";

import { useChat } from "./ChatProvider";

export function ChatHistory({ onPick }: { onPick?: () => void }) {
  const { sessionId, setSessionId } = useChat();
  const sessions = useAgentSessions();
  const remove = useDeleteAgentSession();

  if (sessions.isPending) {
    return (
      <div
        role="status"
        aria-label="Loading conversations"
        className="h-16 animate-pulse rounded-xl bg-gray-100"
      />
    );
  }
  if (sessions.isError) {
    return (
      <p role="alert" className="text-sm text-red-700">
        {sessions.error.message}{" "}
        <button
          type="button"
          className="font-semibold underline"
          onClick={() => void sessions.refetch()}
        >
          Retry
        </button>
      </p>
    );
  }
  if (sessions.data.items.length === 0) {
    return <p className="text-sm text-gray-600">No conversations yet. Ask your first question.</p>;
  }
  return (
    <ul aria-label="Conversations" className="flex flex-col divide-y divide-gray-100">
      {sessions.data.items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-2 py-2">
          <button
            type="button"
            aria-current={item.id === sessionId ? "true" : undefined}
            onClick={() => {
              setSessionId(item.id);
              onPick?.();
            }}
            className={`min-w-0 flex-1 truncate text-left text-sm hover:underline ${
              item.id === sessionId ? "font-bold text-violet-800" : "font-medium text-gray-800"
            }`}
          >
            {item.title}
            <span className="ml-2 text-xs font-normal text-gray-500">
              {new Date(item.updated_at).toLocaleDateString()}
            </span>
          </button>
          <button
            type="button"
            disabled={remove.isPending}
            aria-label={`Delete conversation ${item.title}`}
            onClick={() => {
              remove.mutate(item.id, {
                onSuccess: () => {
                  if (item.id === sessionId) setSessionId(null);
                },
              });
            }}
            className="text-xs font-semibold text-gray-500 hover:text-red-700"
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
}

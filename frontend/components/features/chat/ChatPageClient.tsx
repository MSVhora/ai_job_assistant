"use client";

import { Card } from "@/components/ui/card";

import { ChatConversation } from "./ChatConversation";
import { ChatHistory } from "./ChatHistory";
import { useChat } from "./ChatProvider";
import { ProfileSelect } from "./ProfileSelect";

export function ChatPageClient() {
  const { sessionId, setSessionId } = useChat();
  return (
    <div className="grid gap-5 md:grid-cols-[16rem_1fr]">
      <Card
        title={<h2 className="text-sm font-bold text-gray-900">Conversations</h2>}
        action={
          <button
            type="button"
            onClick={() => {
              setSessionId(null);
            }}
            className="rounded-lg px-2 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50"
          >
            New chat
          </button>
        }
      >
        <ChatHistory />
      </Card>
      <div className="flex min-h-[32rem] flex-col gap-3 rounded-3xl border border-violet-100 bg-white p-5 shadow-sm">
        <div className="flex justify-end">
          <ProfileSelect />
        </div>
        <ChatConversation key={sessionId ?? "new"} sessionId={sessionId} />
      </div>
    </div>
  );
}

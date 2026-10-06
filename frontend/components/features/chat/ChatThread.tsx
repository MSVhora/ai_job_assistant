import type { AgentCitation, AgentMessage } from "@/lib/api";

import { AnswerCard } from "./AnswerCard";

export function ChatThread({
  messages,
  busy,
  onOpenCitation,
  onReask,
}: {
  messages: AgentMessage[];
  busy: boolean;
  onOpenCitation: (citation: AgentCitation) => void;
  onReask: (question: string) => void;
}) {
  return (
    <ol aria-label="Conversation" aria-live="polite" className="flex flex-col gap-4">
      {messages.map((message, index) => {
        if (message.role === "user") {
          return (
            <li key={message.id} className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-br-md bg-violet-600 px-4 py-2.5 text-sm text-white">
                {message.content}
              </p>
            </li>
          );
        }
        return (
          <li key={message.id} className="max-w-[95%]">
            <AnswerCard
              message={message}
              question={messages[index - 1]?.content ?? ""}
              busy={busy}
              onOpenCitation={onOpenCitation}
              onReask={onReask}
            />
          </li>
        );
      })}
      {busy ? (
        <li role="status" className="text-sm text-gray-500">
          Looking through your evidence…
        </li>
      ) : null}
    </ol>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ChatConversation } from "./ChatConversation";
import { ChatHistory } from "./ChatHistory";
import { useChat } from "./ChatProvider";
import { ProfileSelect } from "./ProfileSelect";

export const LAUNCHER_ID = "chat-launcher";

const ACTION =
  "rounded-lg px-2 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600";

export function ChatPanel() {
  const { setOpen, setSessionId, sessionId } = useChat();
  const [history, setHistory] = useState(false);

  const close = () => {
    setOpen(false);
    window.setTimeout(() => document.getElementById(LAUNCHER_ID)?.focus(), 0);
  };
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      const inside = target instanceof Node && panel.current?.contains(target) === true;
      if (event.key === "Escape" && inside) {
        setOpen(false);
        window.setTimeout(() => document.getElementById(LAUNCHER_ID)?.focus(), 0);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [setOpen]);

  return (
    <section
      role="dialog"
      aria-modal="false"
      aria-label="Chat with your evidence"
      ref={panel}
      className="fixed right-4 bottom-24 z-40 flex h-[min(40rem,calc(100vh-7rem))] w-[min(26rem,calc(100vw-2rem))] flex-col gap-3 rounded-3xl border border-violet-100 bg-white p-4 shadow-2xl shadow-violet-300/40 sm:right-6"
    >
      <header className="flex flex-wrap items-center gap-1">
        <h2 className="mr-auto text-sm font-bold text-gray-900">Chat</h2>
        <ProfileSelect />
        <button
          type="button"
          className={ACTION}
          onClick={() => {
            setSessionId(null);
            setHistory(false);
          }}
        >
          New chat
        </button>
        <button
          type="button"
          aria-pressed={history}
          className={ACTION}
          onClick={() => {
            setHistory((value) => !value);
          }}
        >
          History
        </button>
        <Link href="/chat" className={ACTION}>
          Open full page
        </Link>
        <button type="button" aria-label="Close chat" className={ACTION} onClick={close}>
          ✕
        </button>
      </header>
      {history ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <ChatHistory
            onPick={() => {
              setHistory(false);
            }}
          />
        </div>
      ) : (
        <ChatConversation key={sessionId ?? "new"} sessionId={sessionId} />
      )}
    </section>
  );
}

"use client";

import { usePathname } from "next/navigation";

import { ChatPanel, LAUNCHER_ID } from "./ChatPanel";
import { useChat } from "./ChatProvider";

const HIDDEN_ON = ["/", "/get-started", "/chat"];

export function ChatLauncher() {
  const pathname = usePathname();
  const { open, setOpen } = useChat();
  if (HIDDEN_ON.includes(pathname)) return null;
  return (
    <>
      {open ? <ChatPanel /> : null}
      <button
        id={LAUNCHER_ID}
        type="button"
        aria-expanded={open}
        aria-label={open ? "Close chat" : "Open chat"}
        onClick={() => {
          setOpen(!open);
        }}
        className="fixed right-4 bottom-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 text-white shadow-xl shadow-violet-400/50 transition hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 sm:right-6 sm:bottom-6"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="h-6 w-6">
          <path d="M4 4h16a2 2 0 012 2v10a2 2 0 01-2 2H9l-5 4v-4H4a2 2 0 01-2-2V6a2 2 0 012-2z" />
        </svg>
      </button>
    </>
  );
}

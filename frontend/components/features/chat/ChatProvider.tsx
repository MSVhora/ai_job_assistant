"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

const OPEN_KEY = "chat.open";
const SESSION_KEY = "chat.session";
const PROFILE_KEY = "chat.profile";

const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

const memory = new Map<string, string | null>();

function write(key: string, value: string | null) {
  memory.set(key, value);
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // storage can be unavailable (private windows); the in-memory value keeps the chat working
  }
  listeners.forEach((listener) => {
    listener();
  });
}

function snapshot(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return memory.get(key) ?? null;
  }
}

/** A string kept in localStorage; the server snapshot is null so hydration always matches. */
function useStored(key: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => snapshot(key),
    () => null,
  );
}

interface ChatState {
  open: boolean;
  sessionId: string | null;
  profileId: string | null;
  setOpen: (open: boolean) => void;
  setSessionId: (id: string | null) => void;
  setProfileId: (id: string | null) => void;
}

const ChatContext = createContext<ChatState | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const open = useStored(OPEN_KEY) === "1";
  const sessionId = useStored(SESSION_KEY);
  const profileId = useStored(PROFILE_KEY);

  const setOpen = useCallback((value: boolean) => {
    write(OPEN_KEY, value ? "1" : null);
  }, []);
  const setSessionId = useCallback((value: string | null) => {
    write(SESSION_KEY, value);
  }, []);
  const setProfileId = useCallback((value: string | null) => {
    write(PROFILE_KEY, value);
  }, []);

  const value = useMemo(
    () => ({ open, sessionId, profileId, setOpen, setSessionId, setProfileId }),
    [open, sessionId, profileId, setOpen, setSessionId, setProfileId],
  );
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatState {
  const context = useContext(ChatContext);
  if (context === null) throw new Error("useChat must be used inside ChatProvider");
  return context;
}

"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string | undefined;
  children: ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-violet-950/40 backdrop-blur-sm" />
        <DialogPrimitive.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(100vw,52rem)] flex-col overflow-y-auto border-l border-violet-100 bg-white p-6 shadow-2xl shadow-violet-300/40 focus:outline-none sm:p-8">
          <DialogPrimitive.Title className="pr-8 text-lg font-bold tracking-tight text-gray-900">
            {title}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="mt-1 text-sm text-gray-600">
            {description ?? "Review, edit and decide on this achievement."}
          </DialogPrimitive.Description>
          <div className="mt-5 flex flex-col gap-6">{children}</div>
          <DialogPrimitive.Close
            aria-label="Close"
            className="absolute top-4 right-4 rounded-full p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            ✕
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

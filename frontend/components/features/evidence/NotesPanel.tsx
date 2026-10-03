"use client";

import { Card } from "@/components/ui/card";

import { LinkForm } from "./LinkForm";
import { NoteForm } from "./NoteForm";
import { NoteList } from "./NoteList";
import { ResumeIngest } from "./ResumeIngest";

export function NotesPanel() {
  return (
    <Card title={<h2 className="text-base font-bold text-gray-900">Notes, links and resume</h2>}>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-5">
          <NoteForm />
          <LinkForm />
        </div>
        <div className="flex flex-col gap-5">
          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-900">Your notes</h3>
            <NoteList />
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-900">Resume entries</h3>
            <ResumeIngest />
          </div>
        </div>
      </div>
    </Card>
  );
}

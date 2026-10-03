"use client";

import { useState, type SyntheticEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCreateLink } from "@/hooks/use-evidence-sources";

export function LinkForm() {
  const create = useCreateLink();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    if (url.trim() === "") return;
    create.mutate(
      {
        url: url.trim(),
        ...(title.trim() === "" ? {} : { title: title.trim() }),
        ...(text.trim() === "" ? {} : { text: text.trim() }),
      },
      {
        onSuccess: () => {
          setUrl("");
          setTitle("");
          setText("");
          toast.success("Link saved");
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label="Add a link">
      <Field
        label="Link URL"
        htmlFor="link-url"
        hint="Links are never fetched. Paste the relevant text below if you want it used as evidence."
      >
        <Input
          id="link-url"
          type="url"
          value={url}
          placeholder="https://"
          onChange={(event) => {
            setUrl(event.target.value);
          }}
        />
      </Field>
      <Field label="Link title (optional)" htmlFor="link-title">
        <Input
          id="link-title"
          value={title}
          maxLength={200}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
        />
      </Field>
      <Field label="Pasted text (optional)" htmlFor="link-text">
        <Textarea
          id="link-text"
          rows={3}
          value={text}
          maxLength={20000}
          onChange={(event) => {
            setText(event.target.value);
          }}
        />
      </Field>
      <div>
        <Button type="submit" variant="secondary" disabled={create.isPending || url.trim() === ""}>
          Save link
        </Button>
      </div>
    </form>
  );
}

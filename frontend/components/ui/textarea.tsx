import type { TextareaHTMLAttributes } from "react";

import { controlStyles } from "./input";

export function Textarea({
  className,
  rows = 3,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={rows} className={`${controlStyles} ${className ?? ""}`} {...props} />;
}

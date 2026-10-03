export const STEP_LABELS = ["Profile", "Source", "Details", "Review"] as const;
export const LAST_STEP = 4;

export const STEP_FIELDS: string[][] = [
  [],
  ["source"],
  [
    "query.title",
    "query.skills_all",
    "query.skills",
    "query.exclude",
    "location",
    "country",
    "minSalary",
    "maxSalary",
    "posted_within",
    "results_wanted",
  ],
  [],
];

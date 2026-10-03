import type { ReactNode } from "react";

const iconProps = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
  className: "h-4.5 w-4.5",
} as const;

function Svg({ d, children }: { d?: string; children?: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" {...iconProps}>
      {d !== undefined && <path d={d} />}
      {children}
    </svg>
  );
}

export function ContactIcon() {
  return (
    <Svg>
      <path d="M4 6h16v12H4z" />
      <path d="M4 7l8 6 8-6" />
    </Svg>
  );
}

export function HeadlineIcon() {
  return (
    <Svg>
      <path d="M4 6h16M4 12h10M4 18h7" />
    </Svg>
  );
}

export function SkillsIcon() {
  return (
    <Svg>
      <path d="M12 3l2.5 5.5L20 9l-4 4 1 6-5-2.8L7 19l1-6-4-4 5.5-.5z" />
    </Svg>
  );
}

export function ExperienceIcon() {
  return (
    <Svg>
      <rect x="3" y="8" width="18" height="12" rx="2" />
      <path d="M9 8V6a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18" />
    </Svg>
  );
}

export function ProjectsIcon() {
  return (
    <Svg>
      <path d="M4 20V10l8-6 8 6v10" />
      <path d="M10 20v-6h4v6" />
    </Svg>
  );
}

export function EducationIcon() {
  return (
    <Svg>
      <path d="M3 9l9-5 9 5-9 5-9-5z" />
      <path d="M7 11.5V16c0 1.5 2.5 3 5 3s5-1.5 5-3v-4.5" />
    </Svg>
  );
}

export function CertificationsIcon() {
  return (
    <Svg>
      <circle cx="12" cy="9" r="5" />
      <path d="M9 13l-1.5 8L12 19l4.5 2L15 13" />
    </Svg>
  );
}

export function AwardsIcon() {
  return (
    <Svg>
      <path d="M8 21h8M12 17v4" />
      <path d="M7 4h10v4a5 5 0 01-10 0V4z" />
      <path d="M7 6H4a3 3 0 003 3M17 6h3a3 3 0 01-3 3" />
    </Svg>
  );
}

export function ExtraIcon() {
  return (
    <Svg>
      <path d="M6 3h9l4 4v14H6V3z" />
      <path d="M9 12h6M9 16h6M9 8h3" />
    </Svg>
  );
}

export function PreferencesIcon() {
  return (
    <Svg>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="8" cy="17" r="2" />
    </Svg>
  );
}

export function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className={`h-4 w-4 shrink-0 text-gray-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
    >
      <path
        fillRule="evenodd"
        d="M5.3 7.3a1 1 0 011.4 0L10 10.6l3.3-3.3a1 1 0 111.4 1.4l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 010-1.4z"
        clipRule="evenodd"
      />
    </svg>
  );
}

import { UploadIcon, ProfileIcon, KeyIcon, JobsIcon, AtsIcon, BuilderIcon } from "./icons";
import {
  JobSearchPreview,
  UploadPreview,
  ProfilePreview,
  SetupPreview,
  AtsPreview,
  BarsPreview,
} from "./previews";

export interface GetStartedOption {
  eyebrow: string;
  title: string;
  description: string;
  Icon: () => React.ReactElement;
  Preview: () => React.ReactElement;
  href?: string;
  popular?: boolean;
  disabled?: boolean;
}

export const OPTIONS: GetStartedOption[] = [
  {
    eyebrow: "AI JOB SEARCH",
    title: "Create profile",
    description: "Upload a resume and let AI draft your profile for targeted matching.",
    Icon: UploadIcon,
    Preview: UploadPreview,
    href: "/upload",
    popular: false,
  },
  {
    eyebrow: "AI JOB PROFILES",
    title: "Manage profiles",
    description: "Review, edit and manage profile tracks for targeted matching.",
    Icon: ProfileIcon,
    Preview: ProfilePreview,
    href: "/profile",
    popular: false,
  },
  {
    eyebrow: "JOB OPENINGS",
    title: "Job openings",
    description: "Browse ranked openings from every enabled source and act on your matches.",
    Icon: JobsIcon,
    Preview: JobSearchPreview,
    href: "/jobs",
    popular: true,
  },
  {
    eyebrow: "AI ATS SCORE",
    title: "Score & fix your resume",
    description: "Score your resume against applicant tracking systems and get fixes.",
    Icon: AtsIcon,
    Preview: AtsPreview,
    href: "/ats",
  },
  {
    eyebrow: "AI RESUME BUILDER",
    title: "Build tailored resumes",
    description: "Generate tailored, ATS-ready resumes for every application.",
    Icon: BuilderIcon,
    Preview: BarsPreview,
    disabled: true,
  },
  {
    eyebrow: "API SETUP",
    title: "Add your API keys",
    description: "Add Gemini, Adzuna and Apify keys to power AI features and sources.",
    Icon: KeyIcon,
    Preview: SetupPreview,
    href: "/setup",
    popular: false,
  },
];

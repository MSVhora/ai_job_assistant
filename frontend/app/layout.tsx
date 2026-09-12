import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { SiteHeader } from "@/components/features/SiteHeader";
import { Toaster } from "@/components/ui/toast";
import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "JobGen — AI Job Search, Apply Smarter | Resume → Ranked Job Matches",
    template: "%s | JobGen",
  },
  description:
    "JobGen is an AI job search assistant: upload your resume once, review the AI-drafted profile, and get job openings from multiple sources ranked with plain-language explanations. Self-hosted, bring-your-own-key.",
  keywords: [
    "AI job search",
    "job matching",
    "resume to job matches",
    "ATS resume score",
    "job openings ranked",
    "self-hosted job assistant",
    "bring your own key AI",
  ],
  applicationName: "JobGen",
  openGraph: {
    title: "JobGen — AI Job Search, Apply Smarter",
    description:
      "Upload once, review your AI-drafted profile, and get ranked job openings with plain-language explanations of why each role fits.",
    siteName: "JobGen",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "JobGen — AI Job Search, Apply Smarter",
    description:
      "Upload your resume once — AI drafts your profile and ranks job openings from all your sources with explanations.",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full scroll-smooth antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <SiteHeader />
        <Providers>{children}</Providers>
        <Toaster />
      </body>
    </html>
  );
}

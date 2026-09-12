"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

function BackIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <path d="M19 12H5m0 0l6-6m-6 6l6 6" />
    </svg>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const isHome = pathname === "/";
  const isGetStarted = pathname === "/get-started";

  return (
    <header
      className={`sticky top-0 z-40 transition-all duration-300 ${
        scrolled
          ? "border-b border-violet-100 bg-white/90 shadow-sm shadow-violet-100/50 backdrop-blur"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-8">
        <Link
          href="/"
          aria-label="JobGen — go to home"
          className="rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          <Image
            src="/logo.png"
            alt="JobGen"
            width={160}
            height={42}
            unoptimized
            className="h-10 w-auto"
          />
        </Link>
        {isHome && (
          <Link
            href="/get-started"
            className="rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/40 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-violet-500/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Get Started
          </Link>
        )}
        {!isHome && !isGetStarted && (
          <button
            type="button"
            onClick={() => router.back()}
            aria-label="Go back to the previous page"
            className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-5 py-2.5 text-sm font-semibold text-violet-700 shadow-sm shadow-violet-100 transition hover:-translate-y-0.5 hover:shadow-md hover:shadow-violet-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            <BackIcon />
            Back
          </button>
        )}
      </div>
    </header>
  );
}

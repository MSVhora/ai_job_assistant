"use client";

import { useEffect, useRef, useState } from "react";

import { MATCH_STORIES, MatchCard } from "@/components/features/MatchCard";

const CYCLE_MS = 5000;

const POS_CLASSES = [
  "z-30 translate-x-0 rotate-0 scale-100 opacity-100",
  "z-20 translate-x-[60%] rotate-3 scale-95 opacity-0",
  "z-10 translate-x-[60%] scale-95 opacity-0",
  "z-0 -translate-x-[60%] scale-95 opacity-0",
  "z-0 -translate-x-[60%] -rotate-3 scale-95 opacity-0",
] as const;

export function MatchShowcase() {
  const [active, setActive] = useState(0);
  const paused = useRef(false);

  useEffect(() => {
    const id = setInterval(() => {
      if (!paused.current) setActive((current) => (current + 1) % MATCH_STORIES.length);
    }, CYCLE_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="relative mx-auto mt-16 max-w-4xl"
      onMouseEnter={() => {
        paused.current = true;
      }}
      onMouseLeave={() => {
        paused.current = false;
      }}
    >
      <div className="relative min-h-[320px]">
        {MATCH_STORIES.map((story, i) => {
          const pos = (i - active + MATCH_STORIES.length) % MATCH_STORIES.length;
          return (
            <div
              key={story.role}
              aria-hidden={pos !== 0}
              className={`absolute inset-x-0 top-0 transition-all duration-700 ease-in-out ${
                pos === 0 ? "relative" : ""
              } ${POS_CLASSES[pos]}`}
            >
              <MatchCard story={story} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

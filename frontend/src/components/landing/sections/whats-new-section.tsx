"use client";

import MagicBento, { type BentoCardProps } from "@/components/ui/magic-bento";
import { cn } from "@/lib/utils";

import { Section } from "../section";

const COLOR = "#0a0a0a";
const features: BentoCardProps[] = [
  {
    color: COLOR,
    label: "DMX Control",
    title: "Art-Net / sACN",
    description: "Support for industry standard lighting protocols",
  },
  {
    color: COLOR,
    label: "Multi-Universe",
    title: "Universe Management",
    description:
      "Manage multiple DMX universes simultaneously",
  },
  {
    color: COLOR,
    label: "Extensible",
    title: "Skills and Tools",
    description:
      "Plug, play, or even swap built-in tools. Build the lighting system you want.",
  },

  {
    color: COLOR,
    label: "Persistent",
    title: "Project Files",
    description: "Save, load, and manage your lighting projects",
  },
  {
    color: COLOR,
    label: "Flexible",
    title: "Multi-Model Support",
    description: "Doubao, DeepSeek, OpenAI, Gemini, etc.",
  },
  {
    color: COLOR,
    label: "Professional",
    title: "Stage Ready",
    description: "Designed for theaters, concerts, and live events",
  },
];

export function WhatsNewSection({ className }: { className?: string }) {
  return (
    <Section
      className={cn("", className)}
      title="JRAiController Features"
      subtitle="Professional stage lighting control with advanced AI capabilities"
    >
      <div className="flex w-full items-center justify-center">
        <MagicBento data={features} />
      </div>
    </Section>
  );
}
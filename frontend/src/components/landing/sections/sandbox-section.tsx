"use client";

import {
  AnimatedSpan,
  Terminal,
  TypingAnimation,
} from "@/components/ui/terminal";

import { Section } from "../section";

export function SandboxSection({ className }: { className?: string }) {
  return (
    <Section
      className={className}
      title="Agent Runtime Environment"
      subtitle={
        <p>
          JRAiController provides a secure execution environment for AI agents,
          supporting code execution, file management, and long-running tasks
        </p>
      }
    >
      <div className="mt-8 flex w-full max-w-6xl flex-col items-center gap-12 lg:flex-row lg:gap-16">
        <div className="w-full flex-1">
          <Terminal className="h-[360px] w-full">
            <TypingAnimation>$ dmx-device scan</TypingAnimation>
            <AnimatedSpan delay={800} className="text-zinc-400">
              Scanning Art-Net devices...
            </AnimatedSpan>

            <TypingAnimation delay={1200}>
              $ dmx-device add 192.168.1.100
            </TypingAnimation>
            <AnimatedSpan delay={2000} className="text-green-500">
              ✔ Device added: 192.168.1.100
            </AnimatedSpan>

            <TypingAnimation delay={2400}>
              $ sequence create --name "Concert Lights"
            </TypingAnimation>
            <AnimatedSpan delay={3200} className="text-blue-500">
              ✔ Sequence created: Concert Lights
            </AnimatedSpan>

            <TypingAnimation delay={3600}>
              $ sequence play --name "Concert Lights"
            </TypingAnimation>
            <AnimatedSpan delay={4200} className="text-green-500">
              ✔ Sequence playing
            </AnimatedSpan>
            <AnimatedSpan delay={4500} className="text-green-500">
              ✔ DMX Output: 512 channels
            </AnimatedSpan>
          </Terminal>
        </div>

        <div className="w-full flex-1 space-y-6">
          <div className="space-y-4">
            <p className="text-sm font-medium tracking-wider text-purple-400 uppercase">
              Professional
            </p>
            <h2 className="text-4xl font-bold tracking-tight lg:text-5xl">
              Stage Lighting Control
            </h2>
          </div>

          <div className="space-y-4 text-lg text-zinc-400">
            <p>
              JRAiController supports various DMX protocols including Art-Net and
              sACN, enabling precise control over complex lighting setups for
              theaters, concerts, and live events.
            </p>
          </div>

          <div className="flex flex-wrap gap-3 pt-4">
            <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
              Art-Net
            </span>
            <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
              sACN
            </span>
            <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
              DMX512
            </span>
            <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
              RDM
            </span>
          </div>
        </div>
      </div>
    </Section>
  );
}
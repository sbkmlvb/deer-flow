"use client";

import { AuroraText } from "@/components/ui/aurora-text";
import { Button } from "@/components/ui/button";

import { Section } from "../section";

export function CommunitySection() {
  return (
    <Section
      title={
        <AuroraText colors={["#60A5FA", "#A5FA60", "#A560FA"]}>
          JRAiController
        </AuroraText>
      }
      subtitle="Professional stage lighting control solution for theaters, concerts and live events"
    >
      <div className="flex justify-center">
        <Button className="text-xl" size="lg" asChild>
          <a href="/workspace/chats/new">
            开始使用
          </a>
        </Button>
      </div>
    </Section>
  );
}
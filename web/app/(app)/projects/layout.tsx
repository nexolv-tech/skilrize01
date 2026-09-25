import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Briefs",
  description: "Open briefs from clients. Send a proposal, and every milestone is funded before you start.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

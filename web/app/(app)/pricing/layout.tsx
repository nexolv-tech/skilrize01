import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plans and fees",
  description: "What SkilRize costs: buyers pay the listed price, freelancers pay a 10% fee on what they earn, and paid plans are optional.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Services",
  description: "Fixed-price services from verified freelancers, paid through escrow.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

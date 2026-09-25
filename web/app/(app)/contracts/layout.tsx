import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contracts",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

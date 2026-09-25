import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Checkout",
  description: "Review your order and pay into escrow. Your payment is released only when you accept the delivery.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

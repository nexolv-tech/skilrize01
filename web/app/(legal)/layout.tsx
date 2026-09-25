import { MarketingHeader } from "@/components/shell";
import { SiteFooter } from "@/components/site-footer";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <MarketingHeader />
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-5 py-12 sm:py-16">
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}

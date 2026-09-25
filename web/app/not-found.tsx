import type { Metadata } from "next";

import { MarketingHeader } from "@/components/shell";
import { SiteFooter } from "@/components/site-footer";
import { ButtonLink } from "@/components/ui";

export const metadata: Metadata = { title: "Page not found" };

/** Any address that does not exist, in the same frame as every public page. */
export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <MarketingHeader />
      <main id="main" className="mx-auto flex w-full max-w-7xl flex-1 flex-col justify-center px-5 py-20">
        <p className="eyebrow">Error 404</p>
        <h1 className="display-lg mt-4 max-w-[16ch]">This page does not exist.</h1>
        <p className="mt-5 max-w-lg text-[16px] leading-relaxed text-muted">
          The link may be old, or the service or brief it pointed to may have been removed. Nothing
          on your account has changed.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <ButtonLink href="/">Go to the home page</ButtonLink>
          <ButtonLink href="/gigs" variant="secondary">
            Browse services
          </ButtonLink>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

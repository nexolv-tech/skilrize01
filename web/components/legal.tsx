/**
 * The frame every policy page shares: title, the version in force, a plain
 * summary up front, and a table of contents that stays in view on wide
 * screens. Sections are passed as [id, label] so the contents list and the
 * headings can never drift apart.
 */

import { BUSINESS } from "@/lib/business";

export function LegalDocument({
  title,
  summary,
  sections,
  children,
}: {
  title: string;
  summary: React.ReactNode;
  sections: Array<[string, string]>;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-12 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-16">
      <aside className="lg:sticky lg:top-24 lg:self-start">
        <p className="eyebrow">On this page</p>
        <nav aria-label={`${title} contents`} className="mt-4">
          <ol className="space-y-2 text-[13.5px]">
            {sections.map(([id, label]) => (
              <li key={id}>
                <a href={`#${id}`} className="text-muted transition-colors hover:text-fg">
                  {label}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </aside>

      <article>
        <p className="eyebrow">
          Version {BUSINESS.legalVersion} · In effect from {BUSINESS.legalEffective}
        </p>
        <h1 className="display-lg mt-4">{title}</h1>
        <div className="mt-8 max-w-[44rem] rounded-lg border border-line bg-raised p-5 text-[15px] leading-relaxed text-fg">
          <p className="eyebrow mb-2">In short</p>
          {summary}
        </div>
        <div className="legal mt-4">{children}</div>
      </article>
    </div>
  );
}

/** The operator's identity, for the "who we are" section of each policy. */
export function OperatorBlock() {
  const a = BUSINESS.address;
  return (
    <p>
      <strong>{BUSINESS.operator}</strong>
      <br />
      {BUSINESS.operatorType}. Proprietor: {BUSINESS.proprietor}.
      <br />
      {a.line1}, {a.line2}, {a.city}, {a.region}, {a.country}
      <br />
      Email: <a href={`mailto:${BUSINESS.email}`}>{BUSINESS.email}</a> · Phone:{" "}
      <a href={BUSINESS.phoneHref}>{BUSINESS.phone}</a>
    </p>
  );
}

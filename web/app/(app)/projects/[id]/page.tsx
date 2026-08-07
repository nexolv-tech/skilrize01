"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Icon,
  Input,
  Money,
  Skeleton,
  Tag,
  Textarea,
  cn,
} from "@/components/ui";
import {
  contracts,
  marketplace,
  type ProjectDetail,
  type Proposal,
} from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

/* -------------------------------------------------------------------------- */
/* Proposal form — the freelancer's side                                      */
/* -------------------------------------------------------------------------- */

function ProposalForm({
  project,
  onSubmitted,
}: {
  project: ProjectDetail;
  onSubmitted: () => void;
}) {
  const hourly = project.project_type === "hourly";
  const [cover, setCover] = React.useState("");
  const [amount, setAmount] = React.useState("");
  const [days, setDays] = React.useState("");
  const [answers, setAnswers] = React.useState<Record<number, string>>({});

  const submit = useAsyncAction(async () => {
    await marketplace.submitProposal(project.id, {
      cover_letter: cover,
      ...(hourly ? { hourly_rate: amount } : { bid_amount: amount }),
      estimated_days: days ? Number(days) : null,
      answers: project.screening_questions.map((question) => ({
        question: question.id,
        answer: answers[question.id] ?? "",
      })),
    });
    onSubmitted();
  });

  return (
    <Card>
      <CardHeader
        title="Submit a proposal"
        description="Say how you would approach it, what it costs, and how long it takes."
      />
      <form
        className="space-y-5 p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void submit.run();
        }}
      >
        {submit.error && <Alert tone="critical">{submit.error}</Alert>}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label={hourly ? "Your hourly rate" : "Your price for this work"}
            htmlFor="amount"
            required
            error={submit.fieldErrors.bid_amount ?? submit.fieldErrors.hourly_rate}
            hint={
              hourly
                ? `Client range: ${project.rate_min ?? "—"}–${project.rate_max ?? "—"}`
                : `Client budget: ${project.budget_display}`
            }
          >
            <Input
              id="amount"
              type="number"
              min={1}
              step="1"
              required
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder={hourly ? "2500" : "60000"}
            />
          </Field>

          <Field
            label="Estimated delivery"
            htmlFor="days"
            hint="In days. A realistic number beats an optimistic one."
            error={submit.fieldErrors.estimated_days}
          >
            <Input
              id="days"
              type="number"
              min={1}
              value={days}
              onChange={(event) => setDays(event.target.value)}
              placeholder="21"
            />
          </Field>
        </div>

        <Field
          label="Cover letter"
          htmlFor="cover"
          required
          error={submit.fieldErrors.cover_letter}
          hint="Answer the brief directly. Generic templates are visible from a mile away."
        >
          <Textarea
            id="cover"
            rows={6}
            required
            value={cover}
            onChange={(event) => setCover(event.target.value)}
            placeholder="I have built this exact thing before — here is how I would approach yours…"
          />
        </Field>

        {project.screening_questions.length > 0 && (
          <div className="space-y-4 rounded-md border border-line bg-sunken p-4">
            <p className="text-[13px] font-medium text-fg">
              Screening questions
              <span className="ml-1.5 font-normal text-subtle">
                — the client wrote these and reads every answer
              </span>
            </p>
            {project.screening_questions.map((question) => (
              <Field
                key={question.id}
                label={question.text}
                htmlFor={`q-${question.id}`}
                required={question.is_required}
              >
                <Textarea
                  id={`q-${question.id}`}
                  rows={2}
                  required={question.is_required}
                  value={answers[question.id] ?? ""}
                  onChange={(event) =>
                    setAnswers((current) => ({ ...current, [question.id]: event.target.value }))
                  }
                />
              </Field>
            ))}
            {submit.fieldErrors.answers && (
              <p className="text-[13px] text-critical">{submit.fieldErrors.answers}</p>
            )}
          </div>
        )}

        <Button type="submit" size="lg" loading={submit.pending}>
          <Icon name="send" className="size-4" />
          Submit proposal
        </Button>
      </form>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Proposal list — the client's side                                          */
/* -------------------------------------------------------------------------- */

function ProposalRow({
  proposal,
  onChanged,
}: {
  proposal: Proposal;
  onChanged: () => void;
}) {
  const router = useRouter();
  const [expanded, setExpanded] = React.useState(false);

  const shortlist = useAsyncAction(async () => {
    await marketplace.shortlistProposal(proposal.id);
    onChanged();
  });
  const decline = useAsyncAction(async () => {
    await marketplace.declineProposal(proposal.id);
    onChanged();
  });
  const award = useAsyncAction(async () => {
    const contract = await contracts.award({ proposal: proposal.id });
    router.push(`/contracts/${contract.id}`);
  });

  const tone =
    proposal.status === "accepted"
      ? "positive"
      : proposal.status === "shortlisted"
        ? "accent"
        : proposal.status === "declined"
          ? "critical"
          : "neutral";

  return (
    <li className="p-5">
      <div className="flex flex-wrap items-start gap-4">
        <Avatar
          name={proposal.freelancer.display_name}
          src={proposal.freelancer.avatar_url}
          size={40}
        />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/u/${proposal.freelancer.handle}`}
              className="text-[14px] font-medium text-fg underline-offset-2 hover:underline"
            >
              {proposal.freelancer.display_name}
            </Link>
            <Badge tone={tone as "positive" | "accent" | "critical" | "neutral"}>
              {proposal.status}
            </Badge>
            {proposal.freelancer.is_verified_student && (
              <Badge tone="accent">{proposal.freelancer.university_name ?? "Student"}</Badge>
            )}
          </div>
          {proposal.freelancer.headline && (
            <p className="mt-0.5 text-[12.5px] text-subtle">{proposal.freelancer.headline}</p>
          )}

          <p
            className={cn(
              "mt-3 whitespace-pre-wrap text-[13.5px] leading-relaxed text-muted",
              !expanded && "line-clamp-3",
            )}
          >
            {proposal.cover_letter}
          </p>

          {(proposal.cover_letter.length > 240 || proposal.answers.length > 0) && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="mt-1.5 text-[12.5px] font-medium text-accent underline-offset-2 hover:underline"
            >
              {expanded ? "Show less" : "Read full proposal"}
            </button>
          )}

          {expanded && proposal.answers.length > 0 && (
            <dl className="mt-4 space-y-3 rounded-md border border-line bg-sunken p-4">
              {proposal.answers.map((answer) => (
                <div key={answer.question}>
                  <dt className="text-[12.5px] font-medium text-fg">{answer.question_text}</dt>
                  <dd className="mt-0.5 text-[13px] text-muted">{answer.answer}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>

        <div className="shrink-0 text-right">
          <p className="text-[16px] font-semibold text-fg">
            <Money amount={proposal.bid_amount ?? proposal.hourly_rate} />
            {proposal.hourly_rate && (
              <span className="text-[12px] font-normal text-muted">/hr</span>
            )}
          </p>
          {proposal.estimated_days && (
            <p className="text-[12px] text-subtle">in {proposal.estimated_days} days</p>
          )}
          <p className="mt-1 text-[11.5px] text-subtle">{formatRelative(proposal.created_at)}</p>
        </div>
      </div>

      {proposal.status !== "accepted" && proposal.status !== "declined" && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
          <Button size="sm" loading={award.pending} onClick={() => void award.run()}>
            Award contract
          </Button>
          {proposal.status !== "shortlisted" && (
            <Button
              size="sm"
              variant="secondary"
              loading={shortlist.pending}
              onClick={() => void shortlist.run()}
            >
              Shortlist
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            loading={decline.pending}
            onClick={() => void decline.run()}
          >
            Decline
          </Button>
          {(award.error || shortlist.error || decline.error) && (
            <span className="self-center text-[12.5px] text-critical">
              {award.error ?? shortlist.error ?? decline.error}
            </span>
          )}
        </div>
      )}
    </li>
  );
}

/* -------------------------------------------------------------------------- */

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useSession();

  const [justSubmitted, setJustSubmitted] = React.useState(false);

  const { data, loading, reload } = useLoader(async () => {
    const detail = await marketplace.project(params.id);
    // Proposal contents are only fetched for people entitled to see any: the
    // client who posted it, or a freelancer looking at their own bid.
    const proposals =
      detail.is_owner || detail.my_proposal_id
        ? await marketplace.projectProposals(params.id).catch(() => [] as Proposal[])
        : null;
    return { detail, proposals };
  }, [params.id]);

  const project: ProjectDetail | null = data?.detail ?? null;
  const proposals: Proposal[] | null = data?.proposals ?? null;
  const load = reload;

  const publish = useAsyncAction(async () => {
    await marketplace.publishProject(project!.id);
    await load();
  });
  const close = useAsyncAction(async () => {
    await marketplace.closeProject(project!.id);
    await load();
  });

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!project) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="file" className="size-5" />}
          title="This brief is not available"
          description="It may have been withdrawn, or it was never public."
          action={
            <Link href="/projects">
              <Button variant="secondary">Back to open work</Button>
            </Link>
          }
        />
      </Card>
    );
  }

  const hourly = project.project_type === "hourly";

  return (
    <>
      <Link
        href="/projects"
        className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-muted transition-colors hover:text-fg"
      >
        <Icon name="chevronLeft" className="size-3.5" />
        All open work
      </Link>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          {/* Brief */}
          <Card className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={project.status === "open" ? "positive" : "neutral"}>
                    {project.status}
                  </Badge>
                  {project.category && <Badge>{project.category.name}</Badge>}
                  {project.verified_students_only && <Badge tone="accent">Students only</Badge>}
                </div>
                <h1 className="mt-3 text-[26px] font-semibold leading-tight tracking-[-0.025em] text-fg">
                  {project.title}
                </h1>
                <p className="mt-2 text-[13px] text-subtle">
                  {project.published_at
                    ? `Posted ${formatRelative(project.published_at)}`
                    : "Not published yet"}
                  {" · "}
                  {project.proposal_count}{" "}
                  {project.proposal_count === 1 ? "proposal" : "proposals"}
                </p>
              </div>

              <div className="shrink-0 rounded-lg border border-line bg-sunken px-4 py-3 text-right">
                <p className="text-[20px] font-semibold text-fg">
                  <Money amount={project.budget_max ?? project.rate_max} />
                  {hourly && <span className="text-[13px] font-normal text-muted">/hr</span>}
                </p>
                <p className="text-[12px] text-subtle">
                  {hourly ? "Hourly rate" : "Fixed price"}
                </p>
              </div>
            </div>

            <div className="mt-6 whitespace-pre-wrap text-[14.5px] leading-relaxed text-fg">
              {project.description}
            </div>

            {project.skills.length > 0 && (
              <div className="mt-6">
                <p className="mb-2 text-[12.5px] font-medium text-subtle">Skills required</p>
                <div className="flex flex-wrap gap-1.5">
                  {project.skills.map((skill) => (
                    <Tag key={skill.id}>{skill.name}</Tag>
                  ))}
                </div>
              </div>
            )}

            <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-line pt-5 sm:grid-cols-4">
              {[
                ["Experience", project.experience_level],
                ["Project size", project.size],
                hourly
                  ? ["Weekly hours", project.weekly_hours ? `${project.weekly_hours} hrs` : "—"]
                  : [
                      "Duration",
                      project.expected_duration_days
                        ? `~${project.expected_duration_days} days`
                        : "—",
                    ],
                ["Proposals", String(project.proposal_count)],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-[12px] text-subtle">{label}</dt>
                  <dd className="mt-0.5 text-[13.5px] font-medium capitalize text-fg">{value}</dd>
                </div>
              ))}
            </dl>

            {project.is_owner && (
              <div className="mt-6 flex flex-wrap gap-2 border-t border-line pt-5">
                {project.status === "draft" && (
                  <Button loading={publish.pending} onClick={() => void publish.run()}>
                    Publish brief
                  </Button>
                )}
                {project.status === "open" && (
                  <Button
                    variant="secondary"
                    loading={close.pending}
                    onClick={() => void close.run()}
                  >
                    Close to new proposals
                  </Button>
                )}
                <Button variant="ghost" onClick={() => router.push(`/projects/${project.id}/edit`)}>
                  Edit brief
                </Button>
                {(publish.error || close.error) && (
                  <span className="self-center text-[13px] text-critical">
                    {publish.error ?? close.error}
                  </span>
                )}
              </div>
            )}
          </Card>

          {/* Proposals, or the form to write one */}
          {project.is_owner ? (
            <Card>
              <CardHeader
                title={`Proposals (${proposals?.length ?? 0})`}
                description="Sorted with boosted proposals first, then newest."
              />
              {!proposals || proposals.length === 0 ? (
                <EmptyState
                  icon={<Icon name="send" className="size-5" />}
                  title="No proposals yet"
                  description={
                    project.status === "draft"
                      ? "Publish the brief to start receiving proposals."
                      : "Freelancers will appear here as they apply."
                  }
                />
              ) : (
                <ul className="divide-y divide-line">
                  {proposals.map((proposal) => (
                    <ProposalRow key={proposal.id} proposal={proposal} onChanged={load} />
                  ))}
                </ul>
              )}
            </Card>
          ) : justSubmitted || project.my_proposal_id ? (
            <Alert tone="positive" title="Your proposal is in">
              The client can see it now. You can track it from{" "}
              <Link href="/proposals" className="font-medium underline underline-offset-2">
                my proposals
              </Link>
              .
            </Alert>
          ) : project.can_propose ? (
            <ProposalForm
              project={project}
              onSubmitted={() => {
                setJustSubmitted(true);
                void load();
              }}
            />
          ) : (
            <Alert tone="caution" title="You cannot apply to this brief">
              {project.propose_blocked_reason}
              {!user && (
                <>
                  {" "}
                  <Link href="/login" className="font-medium underline underline-offset-2">
                    Sign in
                  </Link>{" "}
                  to continue.
                </>
              )}
            </Alert>
          )}
        </div>

        {/* Client panel */}
        <aside className="space-y-6">
          <Card>
            <CardHeader title="About the client" />
            <div className="space-y-4 p-5">
              <div className="flex items-center gap-3">
                <Avatar
                  name={project.client.display_name}
                  src={project.client.avatar_url}
                  size={44}
                />
                <div className="min-w-0">
                  <p className="truncate text-[14px] font-medium text-fg">
                    {project.client.display_name}
                  </p>
                  {project.client.headline && (
                    <p className="truncate text-[12.5px] text-subtle">
                      {project.client.headline}
                    </p>
                  )}
                </div>
              </div>

              <dl className="space-y-2.5 border-t border-line pt-4 text-[13px]">
                {[
                  ["Location", [project.client.city, project.client.country].filter(Boolean).join(", ") || "—"],
                  ["Member since", new Date(project.client.created_at).getFullYear().toString()],
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between gap-3">
                    <dt className="text-muted">{label}</dt>
                    <dd className="text-right font-medium text-fg">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex gap-3">
              <Icon name="shield" className="mt-0.5 size-4 shrink-0 text-positive" />
              <div>
                <p className="text-[13px] font-medium text-fg">Payment protection</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                  Money is secured before work starts and released when the client accepts the
                  delivery. Never work on an unfunded milestone.
                </p>
              </div>
            </div>
          </Card>
        </aside>
      </div>
    </>
  );
}

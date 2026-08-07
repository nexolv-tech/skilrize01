"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageHeading } from "@/components/shell";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Icon,
  Input,
  Segmented,
  Select,
  Tag,
  Textarea,
} from "@/components/ui";
import { marketplace, type Category, type Skill } from "@/lib/api";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

export default function NewProjectPage() {
  const router = useRouter();
  const { user } = useSession();

  const categoryQuery = useLoader(() => marketplace.categories(), []);
  const categories: Category[] = categoryQuery.data ?? [];
  const [skillOptions, setSkillOptions] = React.useState<Skill[]>([]);
  const [skillQuery, setSkillQuery] = React.useState("");
  const [chosenSkills, setChosenSkills] = React.useState<Skill[]>([]);
  const [questions, setQuestions] = React.useState<string[]>([]);

  const [form, setForm] = React.useState({
    title: "",
    description: "",
    category: "",
    project_type: "fixed" as "fixed" | "hourly",
    budget_min: "",
    budget_max: "",
    rate_min: "",
    rate_max: "",
    weekly_hours: "",
    size: "medium" as "small" | "medium" | "large",
    expected_duration_days: "",
    experience_level: "intermediate" as "entry" | "intermediate" | "expert",
    verified_students_only: false,
  });

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const searchable = skillQuery.trim().length >= 2;
  // Whether to show the list is decided at render; the effect only fetches.
  const visibleSkills = searchable ? skillOptions : [];

  React.useEffect(() => {
    if (!searchable) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      marketplace
        .skills(skillQuery)
        .then((rows) => {
          if (!cancelled) setSkillOptions(rows);
        })
        .catch(() => undefined);
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [skillQuery, searchable]);

  const hourly = form.project_type === "hourly";

  const save = useAsyncAction(async (publish: boolean) => {
    const project = await marketplace.createProject({
      title: form.title,
      description: form.description,
      category: form.category ? Number(form.category) : null,
      project_type: form.project_type,
      budget_min: hourly ? null : form.budget_min || null,
      budget_max: hourly ? null : form.budget_max || null,
      rate_min: hourly ? form.rate_min || null : null,
      rate_max: hourly ? form.rate_max || null : null,
      weekly_hours: hourly && form.weekly_hours ? Number(form.weekly_hours) : null,
      size: form.size,
      expected_duration_days: form.expected_duration_days
        ? Number(form.expected_duration_days)
        : null,
      experience_level: form.experience_level,
      verified_students_only: form.verified_students_only,
      skill_ids: chosenSkills.map((skill) => skill.id),
      screening_questions: questions
        .filter((text) => text.trim())
        .map((text, index) => ({ text, order: index, is_required: true })),
    });

    if (publish) await marketplace.publishProject(project.id);
    router.push(`/projects/${project.id}`);
  });

  if (user && !user.can_transact) {
    return (
      <>
        <PageHeading title="Post a project" />
        <Alert tone="caution" title="Finish your profile first">
          Posting a brief means hiring, and hiring means money moves. Verify your email, phone,
          and identity to unlock it.{" "}
          <Link href="/dashboard" className="font-medium underline underline-offset-2">
            Go to verification
          </Link>
          .
        </Alert>
      </>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeading
        title="Post a project"
        description="A specific brief with a real budget gets better proposals than a vague one with a big number."
      />

      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault();
          void save.run(true);
        }}
      >
        {save.error && <Alert tone="critical">{save.error}</Alert>}

        {/* --- What --- */}
        <Card>
          <CardHeader title="What needs doing" />
          <div className="space-y-5 p-5">
            <Field
              label="Title"
              htmlFor="title"
              required
              error={save.fieldErrors.title}
              hint="One line, specific. “Rebuild our ops dashboard in React” beats “Need a developer”."
            >
              <Input
                id="title"
                required
                maxLength={200}
                value={form.title}
                onChange={(event) => set("title", event.target.value)}
                placeholder="Rebuild our internal operations dashboard"
              />
            </Field>

            <Field
              label="Description"
              htmlFor="description"
              required
              error={save.fieldErrors.description}
              hint="What exists today, what you want instead, and how you will know it is done."
            >
              <Textarea
                id="description"
                rows={8}
                required
                value={form.description}
                onChange={(event) => set("description", event.target.value)}
                placeholder="We run logistics on a spreadsheet and it has stopped scaling…"
              />
            </Field>

            <Field label="Category" htmlFor="category" error={save.fieldErrors.category}>
              <Select
                id="category"
                value={form.category}
                onChange={(event) => set("category", event.target.value)}
              >
                <option value="">Choose a category</option>
                {categories.map((category) => (
                  <optgroup key={category.id} label={category.name}>
                    <option value={category.id}>{category.name} (general)</option>
                    {category.children.map((child) => (
                      <option key={child.id} value={child.id}>
                        {child.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </Field>

            <Field
              label="Skills"
              htmlFor="skills"
              hint="These drive who sees your brief. Two to six is the sweet spot."
            >
              <Input
                id="skills"
                value={skillQuery}
                onChange={(event) => setSkillQuery(event.target.value)}
                placeholder="Start typing — React, Figma, SEO…"
              />
              {visibleSkills.length > 0 && (
                <ul className="mt-2 max-h-44 overflow-y-auto rounded-md border border-line bg-raised p-1 shadow-e2">
                  {visibleSkills
                    .filter((skill) => !chosenSkills.some((chosen) => chosen.id === skill.id))
                    .map((skill) => (
                      <li key={skill.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setChosenSkills((current) => [...current, skill]);
                            setSkillQuery("");
                            setSkillOptions([]);
                          }}
                          className="w-full rounded-sm px-2.5 py-1.5 text-left text-[13px] text-muted transition-colors hover:bg-sunken hover:text-fg"
                        >
                          {skill.name}
                        </button>
                      </li>
                    ))}
                </ul>
              )}
              {chosenSkills.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {chosenSkills.map((skill) => (
                    <Tag
                      key={skill.id}
                      onRemove={() =>
                        setChosenSkills((current) =>
                          current.filter((chosen) => chosen.id !== skill.id),
                        )
                      }
                    >
                      {skill.name}
                    </Tag>
                  ))}
                </div>
              )}
            </Field>
          </div>
        </Card>

        {/* --- Budget --- */}
        <Card>
          <CardHeader
            title="Budget"
            description="Freelancers filter on this. An honest range gets better matches than a placeholder."
          />
          <div className="space-y-5 p-5">
            <Segmented
              label="Pricing model"
              value={form.project_type}
              onChange={(value) => set("project_type", value)}
              options={[
                { value: "fixed", label: "Fixed price" },
                { value: "hourly", label: "Hourly" },
              ]}
            />

            {hourly ? (
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Minimum rate" htmlFor="rate_min" error={save.fieldErrors.rate_min}>
                  <Input
                    id="rate_min"
                    type="number"
                    min={1}
                    value={form.rate_min}
                    onChange={(event) => set("rate_min", event.target.value)}
                    placeholder="2000"
                  />
                </Field>
                <Field
                  label="Maximum rate"
                  htmlFor="rate_max"
                  required
                  error={save.fieldErrors.rate_max}
                >
                  <Input
                    id="rate_max"
                    type="number"
                    min={1}
                    value={form.rate_max}
                    onChange={(event) => set("rate_max", event.target.value)}
                    placeholder="3500"
                  />
                </Field>
                <Field
                  label="Hours per week"
                  htmlFor="weekly_hours"
                  hint="Becomes the contract cap."
                >
                  <Input
                    id="weekly_hours"
                    type="number"
                    min={1}
                    max={168}
                    value={form.weekly_hours}
                    onChange={(event) => set("weekly_hours", event.target.value)}
                    placeholder="10"
                  />
                </Field>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-3">
                <Field
                  label="Minimum budget"
                  htmlFor="budget_min"
                  error={save.fieldErrors.budget_min}
                >
                  <Input
                    id="budget_min"
                    type="number"
                    min={1}
                    value={form.budget_min}
                    onChange={(event) => set("budget_min", event.target.value)}
                    placeholder="40000"
                  />
                </Field>
                <Field
                  label="Maximum budget"
                  htmlFor="budget_max"
                  required
                  error={save.fieldErrors.budget_max}
                >
                  <Input
                    id="budget_max"
                    type="number"
                    min={1}
                    value={form.budget_max}
                    onChange={(event) => set("budget_max", event.target.value)}
                    placeholder="80000"
                  />
                </Field>
                <Field label="Expected duration" htmlFor="duration" hint="In days.">
                  <Input
                    id="duration"
                    type="number"
                    min={1}
                    value={form.expected_duration_days}
                    onChange={(event) => set("expected_duration_days", event.target.value)}
                    placeholder="21"
                  />
                </Field>
              </div>
            )}
          </div>
        </Card>

        {/* --- Who --- */}
        <Card>
          <CardHeader title="Who you are looking for" />
          <div className="grid gap-5 p-5 sm:grid-cols-2">
            <Field label="Experience level" htmlFor="experience_level">
              <Select
                id="experience_level"
                value={form.experience_level}
                onChange={(event) =>
                  set("experience_level", event.target.value as typeof form.experience_level)
                }
              >
                <option value="entry">Entry level</option>
                <option value="intermediate">Intermediate</option>
                <option value="expert">Expert</option>
              </Select>
            </Field>

            <Field label="Project size" htmlFor="size">
              <Select
                id="size"
                value={form.size}
                onChange={(event) => set("size", event.target.value as typeof form.size)}
              >
                <option value="small">Small — a few days</option>
                <option value="medium">Medium — a few weeks</option>
                <option value="large">Large — months</option>
              </Select>
            </Field>

            {user?.is_verified_student && (
              <label className="flex cursor-pointer gap-3 rounded-md border border-line p-3.5 sm:col-span-2">
                <input
                  type="checkbox"
                  checked={form.verified_students_only}
                  onChange={(event) => set("verified_students_only", event.target.checked)}
                  className="mt-0.5 size-4 accent-[var(--accent)]"
                />
                <span>
                  <span className="block text-[13.5px] font-medium text-fg">
                    Verified students only <Badge tone="accent">Campus</Badge>
                  </span>
                  <span className="mt-0.5 block text-[12.5px] text-muted">
                    Only verified students will be able to submit a proposal.
                  </span>
                </span>
              </label>
            )}
          </div>
        </Card>

        {/* --- Screening --- */}
        <Card>
          <CardHeader
            title="Screening questions"
            description="Optional, and the single most effective filter against low-effort proposals."
            action={
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setQuestions((current) => [...current, ""])}
              >
                <Icon name="plus" className="size-3.5" />
                Add
              </Button>
            }
          />
          <div className="space-y-3 p-5">
            {questions.length === 0 && (
              <p className="text-[13px] text-subtle">
                No questions yet. Try: “Link one project like this you have shipped.”
              </p>
            )}
            {questions.map((question, index) => (
              <div key={index} className="flex gap-2">
                <Input
                  aria-label={`Screening question ${index + 1}`}
                  value={question}
                  onChange={(event) =>
                    setQuestions((current) =>
                      current.map((item, position) =>
                        position === index ? event.target.value : item,
                      ),
                    )
                  }
                  placeholder="What similar work have you shipped?"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="md"
                  aria-label="Remove question"
                  onClick={() =>
                    setQuestions((current) => current.filter((_, position) => position !== index))
                  }
                >
                  <Icon name="x" className="size-4" />
                </Button>
              </div>
            ))}
          </div>
        </Card>

        <div className="flex flex-wrap gap-3">
          <Button type="submit" size="lg" loading={save.pending}>
            Publish brief
          </Button>
          <Button
            type="button"
            size="lg"
            variant="secondary"
            loading={save.pending}
            onClick={() => void save.run(false)}
          >
            Save as draft
          </Button>
        </div>
      </form>
    </div>
  );
}

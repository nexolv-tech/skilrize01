"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageHeading } from "@/components/shell";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Field,
  Icon,
  Input,
  Select,
  Textarea,
} from "@/components/ui";
import { gigs, marketplace, type Category, type Tier } from "@/lib/api";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

interface DraftPackage {
  tier: Tier;
  enabled: boolean;
  name: string;
  description: string;
  price: string;
  delivery_days: string;
  revisions: string;
  features: string;
}

const INITIAL_PACKAGES: DraftPackage[] = [
  {
    tier: "basic", enabled: true, name: "Basic", description: "", price: "",
    delivery_days: "3", revisions: "1", features: "",
  },
  {
    tier: "standard", enabled: false, name: "Standard", description: "", price: "",
    delivery_days: "5", revisions: "2", features: "",
  },
  {
    tier: "premium", enabled: false, name: "Premium", description: "", price: "",
    delivery_days: "7", revisions: "3", features: "",
  },
];

export default function NewGigPage() {
  const router = useRouter();
  const { user } = useSession();

  const categoryQuery = useLoader(() => marketplace.categories(), []);
  const categories: Category[] = categoryQuery.data ?? [];

  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [tags, setTags] = React.useState("");
  const [packages, setPackages] = React.useState(INITIAL_PACKAGES);
  const [requirements, setRequirements] = React.useState<string[]>([
    "What do you need, in as much detail as you can give?",
  ]);
  const [extras, setExtras] = React.useState<Array<{ title: string; price: string; days: string }>>(
    [],
  );

  const setPackage = (tier: Tier, patch: Partial<DraftPackage>) =>
    setPackages((current) =>
      current.map((row) => (row.tier === tier ? { ...row, ...patch } : row)),
    );

  const categoryName = categories
    .flatMap((parent) => [parent, ...parent.children.map((c) => ({ ...c, parentName: parent.name }))])
    .find((row) => String(row.id) === category);

  const save = useAsyncAction(async (publish: boolean) => {
    const gig = await gigs.create({
      title,
      description,
      category: category ? Number(category) : null,
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      requirements: requirements
        .filter((label) => label.trim())
        .map((label, index) => ({ key: `req_${index + 1}`, label: label.trim(), required: true })),
      packages: packages
        .filter((row) => row.enabled && row.price)
        .map((row) => ({
          tier: row.tier,
          name: row.name,
          description: row.description,
          price: row.price,
          delivery_days: Number(row.delivery_days),
          revisions: Number(row.revisions),
          features: row.features.split("\n").map((f) => f.trim()).filter(Boolean),
        })),
      extras: extras
        .filter((extra) => extra.title.trim() && extra.price)
        .map((extra) => ({
          title: extra.title.trim(),
          price: extra.price,
          extra_days: Number(extra.days || 0),
        })),
    });

    if (publish) await gigs.publish(gig.id);
    router.push(`/gigs/${gig.id}`);
  });

  if (user && !user.can_transact) {
    return (
      <>
        <PageHeading title="Publish a service" />
        <Alert tone="caution" title="Finish your profile first">
          Selling means being paid, and being paid means we have to know who you are. Verify your
          email, phone, and identity to unlock it.{" "}
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
        title="Publish a service"
        description="A tightly scoped service at a clear price sells far better than a broad one people have to ask about."
      />

      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault();
          void save.run(true);
        }}
      >
        {save.error && <Alert tone="critical">{save.error}</Alert>}

        <Card>
          <CardHeader title="Overview" />
          <div className="space-y-5 p-5">
            <Field
              label="Title"
              htmlFor="title"
              required
              error={save.fieldErrors.title}
              hint="Starts with “I will”. We add it if you forget."
            >
              <Input
                id="title"
                required
                maxLength={190}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="design a complete brand identity for your startup"
              />
            </Field>

            <Field label="Category" htmlFor="category" error={save.fieldErrors.category}>
              <Select
                id="category"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                <option value="">Choose a category</option>
                {categories.map((parent) => (
                  <optgroup key={parent.id} label={parent.name}>
                    <option value={parent.id}>{parent.name} (general)</option>
                    {parent.children.map((child) => (
                      <option key={child.id} value={child.id}>
                        {child.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </Field>

            <Field
              label="Description"
              htmlFor="description"
              required
              error={save.fieldErrors.description}
              hint="What the buyer gets, how you work, and what is out of scope."
            >
              <Textarea
                id="description"
                rows={7}
                required
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="You get a primary logo, a secondary mark, a colour system…"
              />
            </Field>

            <Field
              label="Search tags"
              htmlFor="tags"
              error={save.fieldErrors.tags}
              hint="Up to five, comma separated."
            >
              <Input
                id="tags"
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="logo, branding, identity"
              />
            </Field>
          </div>

          {/* Live preview of the catalogue card, so the seller sees what a
              buyer will see before publishing. */}
          <div className="border-t border-line bg-sunken p-5">
            <p className="mb-3 text-[12.5px] font-medium text-subtle">Catalogue preview</p>
            {/* The same card the catalogue draws: category, title, price. */}
            <div className="max-w-[18rem] rounded-lg border border-line bg-raised p-5">
              <p className="text-[12.5px] text-subtle">
                {categoryName && "parentName" in categoryName
                  ? (categoryName as { parentName: string }).parentName
                  : (categoryName?.name ?? "Category")}
              </p>
              <p className="mt-1.5 line-clamp-2 text-[15.5px] font-semibold leading-snug text-fg">
                {title ? `I will ${title.replace(/^i will /i, "")}` : "I will …"}
              </p>
              <div className="mt-5 flex items-end justify-between gap-3">
                <span className="text-[12.5px] text-subtle">New</span>
                <span className="text-right">
                  <span className="block text-[11.5px] text-subtle">Starting at</span>
                  <span className="text-[16px] font-semibold text-fg">
                    {packages.find((p) => p.enabled && p.price)?.price
                      ? `Rs ${Number(packages.find((p) => p.enabled && p.price)!.price).toLocaleString()}`
                      : "Rs —"}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Packages"
            description="Basic is required. Add tiers only where they genuinely differ — invented differences read as padding."
          />
          <div className="divide-y divide-line">
            {packages.map((row) => (
              <div key={row.tier} className="p-5">
                <label className="flex items-center gap-2.5">
                  <input
                    type="checkbox"
                    checked={row.enabled}
                    disabled={row.tier === "basic"}
                    onChange={(event) => setPackage(row.tier, { enabled: event.target.checked })}
                    className="size-4 accent-[var(--accent)] disabled:opacity-50"
                  />
                  <span className="text-[14px] font-medium capitalize text-fg">{row.tier}</span>
                  {row.tier === "basic" && (
                    <span className="text-[12px] text-subtle">(required)</span>
                  )}
                </label>

                {row.enabled && (
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <Field label="Package name" htmlFor={`${row.tier}-name`}>
                      <Input
                        id={`${row.tier}-name`}
                        value={row.name}
                        onChange={(event) => setPackage(row.tier, { name: event.target.value })}
                      />
                    </Field>
                    <Field label="Price" htmlFor={`${row.tier}-price`} required>
                      <Input
                        id={`${row.tier}-price`}
                        type="number"
                        min={1}
                        required
                        value={row.price}
                        onChange={(event) => setPackage(row.tier, { price: event.target.value })}
                        placeholder="8000"
                      />
                    </Field>
                    <Field label="Delivery (days)" htmlFor={`${row.tier}-days`} required>
                      <Input
                        id={`${row.tier}-days`}
                        type="number"
                        min={1}
                        required
                        value={row.delivery_days}
                        onChange={(event) =>
                          setPackage(row.tier, { delivery_days: event.target.value })
                        }
                      />
                    </Field>
                    <Field label="Revisions included" htmlFor={`${row.tier}-revisions`}>
                      <Input
                        id={`${row.tier}-revisions`}
                        type="number"
                        min={0}
                        value={row.revisions}
                        onChange={(event) =>
                          setPackage(row.tier, { revisions: event.target.value })
                        }
                      />
                    </Field>
                    <Field
                      label="What is included"
                      htmlFor={`${row.tier}-features`}
                      className="sm:col-span-2"
                      hint="One per line."
                    >
                      <Textarea
                        id={`${row.tier}-features`}
                        rows={3}
                        value={row.features}
                        onChange={(event) =>
                          setPackage(row.tier, { features: event.target.value })
                        }
                        placeholder={"1 logo concept\nSource files\nCommercial licence"}
                      />
                    </Field>
                  </div>
                )}
              </div>
            ))}
          </div>
          {save.fieldErrors.packages && (
            <p className="px-5 pb-4 text-[13px] text-critical">{save.fieldErrors.packages}</p>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Paid extras"
            description="Optional add-ons a buyer can attach at checkout."
            action={
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() =>
                  setExtras((current) => [...current, { title: "", price: "", days: "0" }])
                }
              >
                <Icon name="plus" className="size-3.5" />
                Add
              </Button>
            }
          />
          <div className="space-y-3 p-5">
            {extras.length === 0 && (
              <p className="text-[13px] text-subtle">
                None yet. Common ones: source files, commercial licence, faster delivery.
              </p>
            )}
            {extras.map((extra, index) => (
              <div key={index} className="flex flex-wrap gap-2">
                <Input
                  aria-label={`Extra ${index + 1} title`}
                  className="min-w-40 flex-1"
                  value={extra.title}
                  onChange={(event) =>
                    setExtras((current) =>
                      current.map((row, position) =>
                        position === index ? { ...row, title: event.target.value } : row,
                      ),
                    )
                  }
                  placeholder="Source files"
                />
                <Input
                  aria-label={`Extra ${index + 1} price`}
                  type="number"
                  min={1}
                  className="w-28"
                  value={extra.price}
                  onChange={(event) =>
                    setExtras((current) =>
                      current.map((row, position) =>
                        position === index ? { ...row, price: event.target.value } : row,
                      ),
                    )
                  }
                  placeholder="3000"
                />
                <Input
                  aria-label={`Extra ${index + 1} extra days`}
                  type="number"
                  className="w-24"
                  value={extra.days}
                  onChange={(event) =>
                    setExtras((current) =>
                      current.map((row, position) =>
                        position === index ? { ...row, days: event.target.value } : row,
                      ),
                    )
                  }
                  placeholder="+days"
                />
                <Button
                  type="button"
                  variant="ghost"
                  aria-label="Remove extra"
                  onClick={() =>
                    setExtras((current) => current.filter((_, position) => position !== index))
                  }
                >
                  <Icon name="x" className="size-4" />
                </Button>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Requirements"
            description="The questions a buyer answers before your clock starts. This is the single best defence against a vague order."
            action={
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setRequirements((current) => [...current, ""])}
              >
                <Icon name="plus" className="size-3.5" />
                Add
              </Button>
            }
          />
          <div className="space-y-3 p-5">
            {requirements.map((question, index) => (
              <div key={index} className="flex gap-2">
                <Input
                  aria-label={`Requirement ${index + 1}`}
                  value={question}
                  onChange={(event) =>
                    setRequirements((current) =>
                      current.map((item, position) =>
                        position === index ? event.target.value : item,
                      ),
                    )
                  }
                  placeholder="What is the brand called, and who is it for?"
                />
                <Button
                  type="button"
                  variant="ghost"
                  aria-label="Remove requirement"
                  onClick={() =>
                    setRequirements((current) =>
                      current.filter((_, position) => position !== index),
                    )
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
            Publish service
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

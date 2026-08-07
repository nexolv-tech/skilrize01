"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import { StudentVerificationCard } from "@/components/student";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Icon,
  Input,
  Select,
  Textarea,
} from "@/components/ui";
import { auth, uploadFile, type User } from "@/lib/api";
import { useAsyncAction, useSession } from "@/lib/session";

const FACES = [
  {
    icon: "briefcase" as const,
    title: "Seller profile",
    body: "Skills, rate, availability, portfolio, and platform-computed statistics.",
  },
  {
    icon: "user" as const,
    title: "Buyer profile",
    body: "Company details, verified payment method, and hiring history.",
  },
];

const VISIBILITY: Array<[User["profile_visibility"], string, string]> = [
  ["public", "Public", "Anyone can view it, and search engines can index it."],
  ["platform", "Signed-in only", "Visible to people with a SkilRize account."],
  ["private", "Private", "Hidden from everyone but you."],
];

/**
 * The form is seeded from the account exactly once, at mount. The page below
 * gives it `key={user.id}`, so switching account remounts it with fresh values
 * — which is React's own answer to "derive state from props" and avoids an
 * effect that would fight the user's edits mid-typing.
 */
function ProfileForm({ user }: { user: User }) {
  const { setUser, refresh } = useSession();
  const fileRef = React.useRef<HTMLInputElement>(null);
  const [saved, setSaved] = React.useState(false);

  const [form, setForm] = React.useState({
    full_name: user.full_name,
    headline: user.headline,
    bio: user.bio,
    country: user.country,
    city: user.city,
    timezone_name: user.timezone_name,
    profile_visibility: user.profile_visibility,
  });

  const save = useAsyncAction(async () => {
    const updated = await auth.updateMe(form);
    setUser(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  });

  const changeAvatar = useAsyncAction(async (file: File) => {
    await uploadFile("/auth/me/avatar/", file);
    await refresh();
  });

  const update = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  return (
    <div className="space-y-6">
        <Card>
          <CardHeader
            title="Identity"
            description="Your name, photo, and handle across both surfaces."
          />
          <div className="flex flex-wrap items-center gap-5 p-5">
            <Avatar name={user.display_name} src={user.avatar_url} size={72} />
            <div className="min-w-0">
              <p className="text-sm font-medium text-fg">{user.display_name}</p>
              <p className="text-[13px] text-muted">@{user.handle}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void changeAvatar.run(file);
                    event.target.value = "";
                  }}
                />
                <Button
                  size="sm"
                  variant="secondary"
                  loading={changeAvatar.pending}
                  onClick={() => fileRef.current?.click()}
                >
                  Change photo
                </Button>
                <span className="text-[12px] text-subtle">
                  Re-encoded on upload, so location data never survives.
                </span>
              </div>
              {changeAvatar.error && (
                <p className="mt-2 text-[13px] text-critical">{changeAvatar.error}</p>
              )}
            </div>
          </div>
        </Card>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save.run();
          }}
          className="space-y-6"
        >
          <Card>
            <CardHeader title="About you" description="Shown on your public profile." />
            <div className="grid gap-5 p-5 sm:grid-cols-2">
              <Field label="Full name" htmlFor="full_name" error={save.fieldErrors.full_name}>
                <Input
                  id="full_name"
                  value={form.full_name}
                  onChange={(event) => update("full_name", event.target.value)}
                  placeholder="Ahmed Raza"
                />
              </Field>

              <Field
                label="Professional headline"
                htmlFor="headline"
                error={save.fieldErrors.headline}
                hint="One line. What you do."
              >
                <Input
                  id="headline"
                  maxLength={140}
                  value={form.headline}
                  onChange={(event) => update("headline", event.target.value)}
                  placeholder="Full-stack developer · React and Django"
                />
              </Field>

              <Field
                label="Overview"
                htmlFor="bio"
                className="sm:col-span-2"
                error={save.fieldErrors.bio}
                hint="What you do, who you do it for, and what makes working with you different."
              >
                <Textarea
                  id="bio"
                  rows={5}
                  value={form.bio}
                  onChange={(event) => update("bio", event.target.value)}
                />
              </Field>

              <Field
                label="Country"
                htmlFor="country"
                error={save.fieldErrors.country}
                hint="Two-letter code, e.g. PK."
              >
                <Input
                  id="country"
                  maxLength={2}
                  value={form.country}
                  onChange={(event) => update("country", event.target.value.toUpperCase())}
                  placeholder="PK"
                  className="uppercase"
                />
              </Field>

              <Field label="City" htmlFor="city" error={save.fieldErrors.city}>
                <Input
                  id="city"
                  value={form.city}
                  onChange={(event) => update("city", event.target.value)}
                  placeholder="Islamabad"
                />
              </Field>

              <Field
                label="Timezone"
                htmlFor="timezone_name"
                className="sm:col-span-2"
                error={save.fieldErrors.timezone_name}
                hint="Clients see your local time, so they know when to expect a reply."
              >
                <Select
                  id="timezone_name"
                  value={form.timezone_name}
                  onChange={(event) => update("timezone_name", event.target.value)}
                >
                  {["UTC", "Asia/Karachi", "Asia/Dubai", "Europe/London", "America/New_York", "America/Los_Angeles"].map(
                    (zone) => (
                      <option key={zone} value={zone}>
                        {zone}
                      </option>
                    ),
                  )}
                </Select>
              </Field>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Visibility"
              description="Contact details are never shown publicly, and campus activity never appears on your global profile — whichever option you choose."
            />
            <fieldset className="space-y-2 p-5">
              <legend className="sr-only">Profile visibility</legend>
              {VISIBILITY.map(([value, label, description]) => (
                <label
                  key={value}
                  className={`flex cursor-pointer gap-3 rounded-md border p-3.5 transition-colors duration-150 ${
                    form.profile_visibility === value
                      ? "border-accent bg-accent-soft"
                      : "border-line hover:bg-sunken"
                  }`}
                >
                  <input
                    type="radio"
                    name="profile_visibility"
                    value={value}
                    checked={form.profile_visibility === value}
                    onChange={() => update("profile_visibility", value)}
                    className="mt-0.5 size-4 accent-[var(--accent)]"
                  />
                  <span>
                    <span className="block text-[13.5px] font-medium text-fg">{label}</span>
                    <span className="mt-0.5 block text-[12.5px] text-muted">{description}</span>
                  </span>
                </label>
              ))}
            </fieldset>
          </Card>

          {save.error && <Alert tone="critical">{save.error}</Alert>}

          <div className="flex items-center gap-3">
            <Button type="submit" loading={save.pending}>
              Save changes
            </Button>
            {saved && (
              <span className="animate-fade inline-flex items-center gap-1.5 text-[13px] text-positive">
                <Icon name="check" className="size-4" strokeWidth={2.6} />
                Saved
              </span>
            )}
          </div>
        </form>

        <Card>
          <CardHeader
            title="Seller and buyer faces"
            description="One account is both. Rates, skills, and hiring history arrive with the marketplace tracks."
            action={<Badge>Phase 1–2</Badge>}
          />
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            {FACES.map((face) => (
              <div key={face.title} className="rounded-md border border-line bg-sunken p-4">
                <span className="grid size-8 place-items-center rounded-md bg-raised text-muted">
                  <Icon name={face.icon} className="size-4" />
                </span>
                <p className="mt-3 text-[13.5px] font-medium text-fg">{face.title}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{face.body}</p>
              </div>
            ))}
          </div>
        </Card>

        <StudentVerificationCard />
    </div>
  );
}

export default function ProfileSettingsPage() {
  const { user } = useSession();

  return (
    <>
      <PageHeading
        title="Profile"
        description="This is what a client reads before deciding to spend money. It is the most important conversion surface you own."
      />
      {user && <ProfileForm key={user.id} user={user} />}
    </>
  );
}

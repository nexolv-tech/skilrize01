"use client";

/**
 * A service's pictures and video.
 *
 * Every service needs at least one picture to go live (the API enforces it;
 * `Gig.publish_blockers`), up to three, the first being the cover buyers see
 * in the catalogue. One short MP4 is optional and plays first on the service
 * page. Two shapes of the same control:
 *
 * - `MediaPicker` collects files in the publish form, before the service
 *   exists, and shows local previews.
 * - `MediaManager` edits a saved service: each change uploads or removes at
 *   once, and a file waiting on its virus scan says so until it clears.
 */

import * as React from "react";

import { Alert, Button, Icon, cn } from "@/components/ui";
import { gigs, type GigDetail } from "@/lib/api";
import { useAsyncAction } from "@/lib/session";

export const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_VIDEO_BYTES = 20 * 1024 * 1024;
const IMAGE_TYPES = "image/jpeg,image/png,image/webp";

/** Why a chosen file cannot be used, or null. Mirrors the API's checks so
 *  the seller hears about it before waiting on an upload. */
function problemWith(file: File, kind: "image" | "video"): string | null {
  if (kind === "image") {
    if (!IMAGE_TYPES.split(",").includes(file.type)) return `${file.name}: use a JPG, PNG or WebP picture.`;
    if (file.size > MAX_IMAGE_BYTES) return `${file.name} is over 10 MB.`;
  } else {
    if (file.type !== "video/mp4") return `${file.name}: the video must be an MP4 file.`;
    if (file.size > MAX_VIDEO_BYTES) return `${file.name} is over 20 MB — about a minute of video fits.`;
  }
  return null;
}

/** Object URLs for local previews, revoked when the files change. */
function usePreviews(files: File[]) {
  const urls = React.useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);
  React.useEffect(() => () => urls.forEach((url) => URL.revokeObjectURL(url)), [urls]);
  return urls;
}

function ImageTile({
  src,
  cover,
  pending,
  onRemove,
  removeLabel,
  removeDisabled,
}: {
  src: string | null;
  cover: boolean;
  pending?: boolean;
  onRemove: () => void;
  removeLabel: string;
  removeDisabled?: boolean;
}) {
  return (
    <li className="relative aspect-[16/10] overflow-hidden rounded-md border border-fg/25 bg-sunken">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="size-full object-cover" />
      ) : (
        <span className="grid size-full place-items-center px-2 text-center text-[12px] text-subtle">
          {pending ? "Checking for viruses…" : "Not available"}
        </span>
      )}
      {cover && (
        <span className="absolute top-2 left-2 rounded-full bg-fg px-2 py-0.5 text-[11px] font-semibold text-surface">
          Cover
        </span>
      )}
      <button
        type="button"
        onClick={onRemove}
        disabled={removeDisabled}
        aria-label={removeLabel}
        title={removeDisabled ? "A live service keeps at least one picture" : removeLabel}
        className="absolute top-2 right-2 grid size-7 cursor-pointer place-items-center rounded-full bg-surface/90 text-fg shadow-e1 transition-colors hover:bg-critical hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Icon name="x" className="size-3.5" />
      </button>
    </li>
  );
}

function AddTile({ onFiles, disabled }: { onFiles: (files: File[]) => void; disabled?: boolean }) {
  const input = React.useRef<HTMLInputElement>(null);
  return (
    <li>
      <input
        ref={input}
        type="file"
        accept={IMAGE_TYPES}
        multiple
        className="sr-only"
        onChange={(event) => {
          onFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        className="grid aspect-[16/10] w-full cursor-pointer place-items-center rounded-md border border-dashed border-fg/35 text-[13px] font-medium text-muted transition-colors hover:border-fg hover:text-fg disabled:cursor-wait disabled:opacity-60"
      >
        <span className="flex flex-col items-center gap-1.5">
          <Icon name="plus" className="size-5" />
          Add picture
        </span>
      </button>
    </li>
  );
}

function VideoSlot({
  src,
  pending,
  onChoose,
  onRemove,
  busy,
}: {
  src: string | null;
  pending: boolean;
  onChoose: (file: File) => void;
  onRemove: (() => void) | null;
  busy?: boolean;
}) {
  const input = React.useRef<HTMLInputElement>(null);
  return (
    <div>
      <input
        ref={input}
        type="file"
        accept="video/mp4"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onChoose(file);
          event.target.value = "";
        }}
      />
      {src || pending ? (
        <div className="flex flex-wrap items-start gap-4">
          <div className="aspect-video w-full max-w-sm overflow-hidden rounded-md border border-fg/25 bg-sunken">
            {src ? (
              <video src={`${src}#t=0.1`} controls preload="metadata" className="size-full bg-black object-contain" />
            ) : (
              <span className="grid size-full place-items-center text-[12px] text-subtle">
                Checking for viruses…
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="secondary" loading={busy} onClick={() => input.current?.click()}>
              Replace video
            </Button>
            {onRemove && (
              <Button type="button" size="sm" variant="ghost" onClick={onRemove}>
                Remove
              </Button>
            )}
          </div>
        </div>
      ) : (
        <Button type="button" size="sm" variant="secondary" loading={busy} onClick={() => input.current?.click()}>
          <Icon name="video" className="size-4" />
          Add a video
        </Button>
      )}
    </div>
  );
}

function Hints() {
  return (
    <p className="text-[12.5px] leading-relaxed text-subtle">
      Pictures: JPG, PNG or WebP, up to 10 MB each — 1280 × 800 or larger looks best. Video:
      MP4, up to 20 MB (about a minute). Show your real work; stock photos and other people&apos;s
      images are not allowed.
    </p>
  );
}

/* -------------------------------------------------------------------------- */
/* In the publish form, before the service exists                             */
/* -------------------------------------------------------------------------- */

export function MediaPicker({
  images,
  onImages,
  video,
  onVideo,
}: {
  images: File[];
  onImages: (files: File[]) => void;
  video: File | null;
  onVideo: (file: File | null) => void;
}) {
  const [problem, setProblem] = React.useState<string | null>(null);
  const previews = usePreviews(images);
  const videoFiles = React.useMemo(() => (video ? [video] : []), [video]);
  const [videoPreview] = usePreviews(videoFiles);

  function addImages(files: File[]) {
    const bad = files.map((file) => problemWith(file, "image")).find(Boolean);
    if (bad) return setProblem(bad);
    if (images.length + files.length > MAX_IMAGES)
      return setProblem(`Up to ${MAX_IMAGES} pictures — remove one to add another.`);
    setProblem(null);
    onImages([...images, ...files]);
  }

  return (
    <div className="space-y-5">
      {problem && <Alert tone="critical">{problem}</Alert>}
      <div>
        <p className="text-[13px] font-medium text-fg">
          Pictures <span className="text-critical">*</span>{" "}
          <span className="font-normal text-subtle">
            — at least one, up to {MAX_IMAGES}. The first is your cover.
          </span>
        </p>
        <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {images.map((file, index) => (
            <ImageTile
              key={`${file.name}-${file.size}-${index}`}
              src={previews[index] ?? null}
              cover={index === 0}
              removeLabel={`Remove ${file.name}`}
              onRemove={() => onImages(images.filter((_, i) => i !== index))}
            />
          ))}
          {images.length < MAX_IMAGES && <AddTile onFiles={addImages} />}
        </ul>
      </div>
      <div>
        <p className="mb-3 text-[13px] font-medium text-fg">
          Video <span className="font-normal text-subtle">— optional</span>
        </p>
        <VideoSlot
          src={videoPreview ?? null}
          pending={false}
          onChoose={(file) => {
            const bad = problemWith(file, "video");
            if (bad) return setProblem(bad);
            setProblem(null);
            onVideo(file);
          }}
          onRemove={video ? () => onVideo(null) : null}
        />
      </div>
      <Hints />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* On a saved service                                                         */
/* -------------------------------------------------------------------------- */

export function MediaManager({
  gig,
  onChange,
}: {
  gig: GigDetail;
  onChange: (next: GigDetail) => void;
}) {
  const [problem, setProblem] = React.useState<string | null>(null);
  const live = gig.status === "active";
  const pending =
    gig.images.some((image) => image.status === "pending") || gig.video_status === "pending";

  // A new upload is scanned in the background; look again until it clears.
  React.useEffect(() => {
    if (!pending) return;
    const timer = window.setTimeout(() => {
      void gigs.detail(gig.id).then(onChange).catch(() => undefined);
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [pending, gig, onChange]);

  const upload = useAsyncAction(async (files: File[]) => {
    onChange(await gigs.addImages(gig.id, files));
  });
  const remove = useAsyncAction(async (fileId: number) => {
    onChange(await gigs.removeImage(gig.id, fileId));
  });
  const setVideo = useAsyncAction(async (file: File) => {
    onChange(await gigs.setVideo(gig.id, file));
  });
  const removeVideo = useAsyncAction(async () => {
    onChange(await gigs.removeVideo(gig.id));
  });
  const error = problem ?? upload.error ?? remove.error ?? setVideo.error ?? removeVideo.error;

  return (
    <div className="space-y-5">
      {error && <Alert tone="critical">{error}</Alert>}
      <div>
        <p className="text-[13px] font-medium text-fg">
          Pictures{" "}
          <span className="font-normal text-subtle">
            — {gig.images.length} of {MAX_IMAGES}. The first is your cover.
          </span>
        </p>
        <ul className={cn("mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3", upload.pending && "opacity-70")}>
          {gig.images.map((image, index) => (
            <ImageTile
              key={image.id}
              src={image.url}
              cover={index === 0}
              pending={image.status === "pending"}
              removeLabel={`Remove picture ${index + 1}`}
              removeDisabled={live && gig.images.length === 1}
              onRemove={() => void remove.run(image.id)}
            />
          ))}
          {gig.images.length < MAX_IMAGES && (
            <AddTile
              disabled={upload.pending}
              onFiles={(files) => {
                const bad = files.map((file) => problemWith(file, "image")).find(Boolean);
                if (bad) return setProblem(bad);
                if (gig.images.length + files.length > MAX_IMAGES)
                  return setProblem(`Up to ${MAX_IMAGES} pictures — remove one to add another.`);
                setProblem(null);
                void upload.run(files);
              }}
            />
          )}
        </ul>
      </div>
      <div>
        <p className="mb-3 text-[13px] font-medium text-fg">
          Video <span className="font-normal text-subtle">— optional</span>
        </p>
        <VideoSlot
          src={gig.video_url}
          pending={gig.video_status === "pending"}
          busy={setVideo.pending}
          onChoose={(file) => {
            const bad = problemWith(file, "video");
            if (bad) return setProblem(bad);
            setProblem(null);
            void setVideo.run(file);
          }}
          onRemove={gig.video_status ? () => void removeVideo.run() : null}
        />
      </div>
      <Hints />
    </div>
  );
}

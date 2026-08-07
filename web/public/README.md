# Static assets

Anything in this folder is served from the site root: `public/hero.mp4` is
reachable at `/hero.mp4`.

## Hero video (optional)

The landing hero ships with an animated gradient field. It is the default, not
a placeholder — it downloads nothing, cannot be blocked by an autoplay policy,
and honours reduced-motion preferences.

To use real footage instead, drop the files here and point the app at them:

```bash
# web/.env.local
NEXT_PUBLIC_HERO_VIDEO=/hero.mp4
NEXT_PUBLIC_HERO_POSTER=/hero-poster.jpg
```

The player is muted, looping, inline, and marked decorative, with a scrim over
the top so headline contrast never depends on what the footage happens to show.

What works well here: slow, wide, low-contrast footage of people working —
nothing with fast cuts or hard text, both of which fight the headline sitting on
top of it.

Practical limits: **under ~3 MB**, H.264 MP4, 1920×1080 or smaller, 8–15
seconds, and cut so the last frame matches the first or the loop will visibly
jump. Always ship the poster; without it the hero is blank until the first frame
decodes.

## Gig and category imagery

Listings do not need image files. Every gig renders deterministic vector cover
art derived from its id and category (`components/artwork.tsx`), so a brand-new
catalogue still looks like a real product. A seller's uploaded cover replaces it
automatically — uploads go through the validated pipeline into private storage,
not into this folder.

## Brand marks

Favicon, app icons, and OG images belong here when they exist. Until then Next
serves its defaults, and the SkilRize wordmark is drawn as inline SVG in
`components/ui.tsx`, so it stays crisp and theme-aware at any size.

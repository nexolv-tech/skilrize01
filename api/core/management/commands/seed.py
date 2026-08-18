"""
Seed the category and skill taxonomy, and optionally a demo dataset.

    python manage.py seed             # taxonomy only — safe on any environment
    python manage.py seed --demo      # plus sample users, briefs, and a contract

The taxonomy is real reference data the product needs in every environment.
The demo flag is for local work and disposable test deployments only, and
refuses to run anywhere else, because seeding fake users into production is
exactly the kind of thing that happens once and is never fully cleaned up.
Two things unlock it: DEBUG=True (local work), or ENVIRONMENT=test (D44's
free Render+Vercel deployment, which runs DEBUG=False like real production
does but sets ENVIRONMENT=test specifically so this can still run there —
render.yaml sets it, deploy/production.env.example sets ENVIRONMENT=production
instead, so the real deployment can never match this by accident).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.scope import GLOBAL_SCOPE, use_scope

TAXONOMY: dict[str, tuple[str, str, list[str]]] = {
    "Development & IT": (
        "code",
        "Web, mobile, and everything that runs behind them",
        ["Web Development", "Mobile Apps", "Backend & APIs", "DevOps & Cloud", "QA & Testing"],
    ),
    "Design & Creative": (
        "palette",
        "Brand, product, and everything people actually look at",
        ["Logo & Brand", "UI/UX Design", "Illustration", "Presentation Design", "Packaging"],
    ),
    "Writing & Translation": (
        "pen",
        "Words that carry weight, in any language",
        ["Copywriting", "Technical Writing", "Translation", "Proofreading", "Ghostwriting"],
    ),
    "Video & Animation": (
        "video",
        "Motion, edit, and post-production",
        ["Video Editing", "Motion Graphics", "Explainer Videos", "Subtitles"],
    ),
    "Marketing & Sales": (
        "megaphone",
        "Getting found, and getting bought",
        ["SEO", "Social Media", "Paid Ads", "Email Marketing", "Content Strategy"],
    ),
    "Data & Analytics": (
        "chart",
        "Turning what you have into what you know",
        ["Data Analysis", "Dashboards & BI", "Data Engineering", "Machine Learning"],
    ),
    "Business & Admin": (
        "briefcase",
        "The work that keeps the work running",
        ["Virtual Assistance", "Bookkeeping", "Project Management", "Market Research"],
    ),
    "Academic Support": (
        "book",
        "Tutoring, research support, and study skills",
        ["Tutoring", "Research Assistance", "Presentation Prep", "Study Notes"],
    ),
}

#: Shared by every demo account. Must satisfy the live password policy —
#: 12 characters with all four character classes and no runs or walks — because
#: the seed sets it through the same hasher every real password goes through.
DEMO_PASSWORD = "Demo-Account9-Pass"  # noqa: S105 — local demo fixture

SKILLS = [
    "React",
    "Next.js",
    "TypeScript",
    "Python",
    "Django",
    "Node.js",
    "Flutter",
    "React Native",
    "PostgreSQL",
    "Docker",
    "AWS",
    "Figma",
    "Adobe Illustrator",
    "Photoshop",
    "After Effects",
    "Premiere Pro",
    "Blender",
    "Copywriting",
    "SEO",
    "Google Ads",
    "Meta Ads",
    "Excel",
    "Power BI",
    "Tableau",
    "Pandas",
    "TensorFlow",
    "WordPress",
    "Shopify",
    "Webflow",
    "Canva",
]


class Command(BaseCommand):
    help = "Seed reference taxonomy, and optionally a local demo dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo", action="store_true", help="Also create sample users and marketplace data."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from marketplace.models import Category, Skill

        created_categories = 0
        for index, (name, (icon, description, children)) in enumerate(TAXONOMY.items()):
            parent, made = Category.objects.get_or_create(
                name=name,
                parent=None,
                defaults={"icon": icon, "description": description, "order": index},
            )
            created_categories += int(made)
            for child_index, child in enumerate(children):
                _, child_made = Category.objects.get_or_create(
                    name=child, parent=parent, defaults={"order": child_index}
                )
                created_categories += int(child_made)

        created_skills = sum(int(Skill.objects.get_or_create(name=name)[1]) for name in SKILLS)

        self.stdout.write(
            self.style.SUCCESS(
                f"Taxonomy ready: {created_categories} categories and "
                f"{created_skills} skills created."
            )
        )

        if options["demo"]:
            self._seed_demo()

    def _seed_demo(self):
        if not (settings.DEBUG or settings.ENVIRONMENT == "test"):
            raise CommandError(
                "Refusing to seed demo data outside DEBUG or a test deployment (ENVIRONMENT=test)."
            )

        from accounts.models import SellerProfile, User, VerificationStatus
        from marketplace.models import Category, Project, ProjectType, Skill

        def make(email: str, name: str, headline: str = "") -> User:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": name,
                    "headline": headline,
                    "handle": User.generate_handle(email),
                    "email_verified": True,
                    "phone_verified": True,
                    "identity_status": VerificationStatus.VERIFIED,
                    "country": "PK",
                    "city": "Islamabad",
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                SellerProfile.objects.get_or_create(user=user)
            return user

        client_user = make("client@skilrize.dev", "Ayesha Khan", "Founder, Northline Logistics")
        make("dev@skilrize.dev", "Bilal Ahmed", "Full-stack developer · React and Django")
        make("designer@skilrize.dev", "Sana Mir", "Brand and product designer")
        make("writer@skilrize.dev", "Hamza Sheikh", "Copywriter and technical writer")
        make("editor@skilrize.dev", "Ayaan Raza", "Video editor and motion designer")
        make("marketer@skilrize.dev", "Zara Malik", "Growth marketer · SEO and paid ads")
        make("analyst@skilrize.dev", "Usman Tariq", "Data analyst · dashboards and BI")
        make("va@skilrize.dev", "Mahnoor Iqbal", "Virtual assistant and ops support")
        make("tutor@skilrize.dev", "Fatima Noor", "Tutor · maths, stats, and test prep")

        briefs = [
            (
                "Rebuild our internal operations dashboard",
                "We run logistics on a spreadsheet and it has stopped scaling. We need a "
                "React dashboard over our existing Django API: shipment tracking, driver "
                "assignment, and a daily exceptions view.",
                "Development & IT",
                ProjectType.FIXED,
                120000,
                220000,
                ["React", "Django", "PostgreSQL"],
            ),
            (
                "Brand identity for a fintech launch",
                "Logo, colour system, typography, and a one-page usage guide. We have "
                "positioning written already and need it turned into something we can ship.",
                "Design & Creative",
                ProjectType.FIXED,
                45000,
                90000,
                ["Figma", "Adobe Illustrator"],
            ),
            (
                "Ongoing SEO and content support",
                "Roughly ten hours a week: keyword research, on-page fixes, and two long-form "
                "articles a month for a B2B SaaS in the compliance space.",
                "Marketing & Sales",
                ProjectType.HOURLY,
                None,
                None,
                ["SEO", "Copywriting"],
            ),
        ]

        with use_scope(GLOBAL_SCOPE):
            for title, description, category_name, kind, low, high, skills in briefs:
                if Project.objects.filter(title=title).exists():
                    continue
                project = Project.objects.create(
                    client=client_user,
                    title=title,
                    description=description,
                    category=Category.objects.filter(name=category_name, parent=None).first(),
                    project_type=kind,
                    budget_min=Decimal(low) if low else None,
                    budget_max=Decimal(high) if high else None,
                    rate_min=Decimal("2000") if kind == ProjectType.HOURLY else None,
                    rate_max=Decimal("3500") if kind == ProjectType.HOURLY else None,
                    weekly_hours=10 if kind == ProjectType.HOURLY else None,
                    status=Project.Status.OPEN,
                )
                project.skills.set(Skill.objects.filter(name__in=skills))
                project.publish()

        self._seed_gigs()

        self.stdout.write(
            self.style.SUCCESS(
                # Read from the constant rather than repeated as a literal, so
                # this line cannot drift out of step with the password actually
                # set — which is exactly what happened when the policy changed.
                f"Demo data ready. Sign in as client@skilrize.dev / {DEMO_PASSWORD}"
            )
        )

    def _seed_gigs(self):
        """A starter catalogue, so the browse grid is not empty on first run.

        One seller per category, each with a dozen gigs sharing that
        category's tier pricing and intake questions — real platforms
        cluster around a handful of price bands per category rather than
        pricing every listing bespoke, and a shared intake question set per
        category is exactly what most sellers in the same line of work
        actually ask.
        """
        from accounts.models import User
        from gigs.models import Gig, Package
        from marketplace.models import Category

        # tiers: (name, price, delivery_days, revisions), always three —
        # basic/standard/premium, in that order.
        catalog = {
            "Development & IT": {
                "seller": "dev@skilrize.dev",
                "tiers": [
                    ("Basic", 18000, 5, 1),
                    ("Standard", 55000, 12, 2),
                    ("Premium", 140000, 25, 3),
                ],
                "questions": [
                    "What should the end product do, in plain language?",
                    "Do you have existing code or specs to share?",
                ],
                "gigs": [
                    (
                        "I will build a responsive web app in React and Django",
                        "A production-ready build: typed front end, REST API, Postgres, auth, "
                        "and a deploy pipeline. Fixed scope, fixed price, no surprises.",
                        ["react", "django", "fullstack"],
                    ),
                    (
                        "I will write clean technical documentation for your API",
                        "Reference docs, a getting-started guide, and runnable examples. I "
                        "read the code rather than guessing from the endpoint names.",
                        ["documentation", "api", "technical writing"],
                    ),
                    (
                        "I will build a REST API backend in Django and PostgreSQL",
                        "A typed, tested API with auth, pagination, and OpenAPI docs — ready for a "
                        "mobile or web client to build against.",
                        ["django", "rest-api", "postgresql"],
                    ),
                    (
                        "I will develop a cross-platform mobile app in Flutter",
                        "One codebase, iOS and Android both, wired to your existing backend or a "
                        "new one.",
                        ["flutter", "mobile", "cross-platform"],
                    ),
                    (
                        "I will set up CI/CD pipelines with GitHub Actions and Docker",
                        "Push to deploy: automated tests, builds, and zero-downtime releases.",
                        ["ci-cd", "docker", "devops"],
                    ),
                    (
                        "I will migrate your app to AWS and set up auto-scaling",
                        "From a single server to a resilient, scaling stack — EC2, RDS, and a load "
                        "balancer configured properly.",
                        ["aws", "devops", "scaling"],
                    ),
                    (
                        "I will fix bugs and optimize a slow Django or React codebase",
                        "I read the code, find what's actually slow or broken, and fix it — not "
                        "guess.",
                        ["debugging", "performance", "django"],
                    ),
                    (
                        "I will build a Shopify or WooCommerce store from scratch",
                        "Theme, product catalogue, checkout, and payment gateway, live and "
                        "selling.",
                        ["shopify", "woocommerce", "ecommerce"],
                    ),
                    (
                        "I will integrate Stripe or a payment gateway into your app",
                        "Checkout, webhooks, and refund handling done correctly the first time.",
                        ["stripe", "payments", "api-integration"],
                    ),
                    (
                        "I will write automated tests for your Python or JS codebase",
                        "Unit and integration tests that catch real regressions, not just coverage "
                        "numbers.",
                        ["testing", "python", "javascript"],
                    ),
                    (
                        "I will build a Chrome extension for your workflow",
                        "From idea to the Chrome Web Store — manifest v3, no shortcuts.",
                        ["chrome-extension", "javascript", "browser"],
                    ),
                    (
                        "I will set up a self-hosted server with Docker and Nginx",
                        "A production-ready VPS setup: reverse proxy, TLS, and containers that "
                        "restart themselves.",
                        ["docker", "nginx", "self-hosted"],
                    ),
                ],
            },
            "Design & Creative": {
                "seller": "designer@skilrize.dev",
                "tiers": [
                    ("Basic", 8000, 4, 2),
                    ("Standard", 22000, 8, 3),
                    ("Premium", 55000, 15, 5),
                ],
                "questions": [
                    "What is the brand or project called, and who is it for?",
                    "Share two examples whose style you like, and say why.",
                ],
                "gigs": [
                    (
                        "I will design a complete brand identity for your startup",
                        "You get a primary logo, a secondary mark, a colour system, type choices, "
                        "and a one-page usage guide. I work in two rounds: three directions first, "
                        "then we refine the one you pick.",
                        ["logo", "branding", "identity"],
                    ),
                    (
                        "I will design a modern, responsive website UI in Figma",
                        "Every screen, every state — ready to hand to a developer or build myself.",
                        ["figma", "ui-design", "web-design"],
                    ),
                    (
                        "I will design your app's UI/UX from wireframe to prototype",
                        "User flows, wireframes, and a clickable prototype your users can "
                        "actually test.",
                        ["ux", "ui-design", "prototyping"],
                    ),
                    (
                        "I will redesign your outdated website to look current",
                        "Same content, a design that doesn't look like 2015.",
                        ["web-design", "redesign", "figma"],
                    ),
                    (
                        "I will design a pitch deck that gets investors to read past slide one",
                        "Structure, visuals, and a narrative that actually lands.",
                        ["pitch-deck", "presentation", "branding"],
                    ),
                    (
                        "I will design packaging for your physical product",
                        "Print-ready dielines, not just a pretty mockup.",
                        ["packaging", "print-design", "branding"],
                    ),
                    (
                        "I will illustrate a custom set of icons for your app",
                        "A consistent icon set, in the style your product actually needs.",
                        ["icon-design", "illustration", "ui-design"],
                    ),
                    (
                        "I will design social media templates for your brand",
                        "A reusable template pack so every post looks like it's from the same "
                        "brand.",
                        ["social-media", "templates", "branding"],
                    ),
                    (
                        "I will design a professional resume and LinkedIn banner",
                        "A resume that gets past the six-second skim, not just a font swap.",
                        ["resume-design", "linkedin", "branding"],
                    ),
                    (
                        "I will create a style guide and design system in Figma",
                        "Tokens, components, and rules — so design and dev stop disagreeing on "
                        "spacing.",
                        ["design-system", "figma", "ui-design"],
                    ),
                    (
                        "I will design your book or magazine cover",
                        "Print and ebook formats, sized correctly for both.",
                        ["cover-design", "print-design", "publishing"],
                    ),
                    (
                        "I will create custom illustrations for your website or app",
                        "Original artwork in a consistent style, not stock.",
                        ["illustration", "custom-art", "branding"],
                    ),
                ],
            },
            "Writing & Translation": {
                "seller": "writer@skilrize.dev",
                "tiers": [
                    ("Basic", 4500, 3, 2),
                    ("Standard", 13000, 6, 3),
                    ("Premium", 32000, 12, 4),
                ],
                "questions": [
                    "What is the piece for, and who will read it?",
                    "Any tone, length, or keyword requirements?",
                ],
                "gigs": [
                    (
                        "I will write SEO-optimized blog posts that actually rank",
                        "Researched, structured, and written for the person searching — not the "
                        "algorithm.",
                        ["seo", "blogging", "content-writing"],
                    ),
                    (
                        "I will write product descriptions that convert browsers to buyers",
                        "Benefit-led copy for your whole catalogue, in your brand's voice.",
                        ["copywriting", "ecommerce", "product-descriptions"],
                    ),
                    (
                        "I will write and edit your website's core pages",
                        "Home, About, and Services — copy that says what you do in one read.",
                        ["web-copy", "copywriting", "editing"],
                    ),
                    (
                        "I will translate documents between English and Urdu",
                        "Certified-quality translation, reviewed for tone as well as accuracy.",
                        ["translation", "urdu", "localization"],
                    ),
                    (
                        "I will ghostwrite LinkedIn posts that build your personal brand",
                        "A month of posts in your voice, based on a single call.",
                        ["linkedin", "ghostwriting", "personal-brand"],
                    ),
                    (
                        "I will proofread and edit your manuscript or thesis",
                        "Line-by-line editing for clarity, grammar, and consistency.",
                        ["proofreading", "editing", "academic-writing"],
                    ),
                    (
                        "I will write a press release for your launch or announcement",
                        "Structured the way journalists actually expect, not marketing fluff.",
                        ["press-release", "pr", "copywriting"],
                    ),
                    (
                        "I will write email sequences that nurture leads into customers",
                        "A welcome series or launch sequence, written to be opened and read.",
                        ["email-marketing", "copywriting", "sales-funnel"],
                    ),
                    (
                        "I will write a script for your explainer or promo video",
                        "Tight, spoken-word copy timed to your video's actual length.",
                        ["scriptwriting", "video", "copywriting"],
                    ),
                    (
                        "I will write your resume, cover letter, and LinkedIn summary",
                        "Three documents that tell one consistent, compelling story.",
                        ["resume-writing", "career", "linkedin"],
                    ),
                    (
                        "I will write technical articles for developer audiences",
                        "Written by someone who's read the docs, not just the marketing page.",
                        ["technical-writing", "developer-content", "blogging"],
                    ),
                    (
                        "I will write UX copy and microcopy for your app",
                        "Every button, error, and empty state — worded like a person wrote it.",
                        ["ux-writing", "microcopy", "product-copy"],
                    ),
                ],
            },
            "Video & Animation": {
                "seller": "editor@skilrize.dev",
                "tiers": [
                    ("Basic", 6000, 3, 2),
                    ("Standard", 18000, 7, 3),
                    ("Premium", 45000, 14, 4),
                ],
                "questions": [
                    "Link the raw footage or source files.",
                    "What is the hook or key message in the first few seconds?",
                ],
                "gigs": [
                    (
                        "I will edit your short-form video for social",
                        "Cuts, captions, colour, and sound. Delivered in vertical and square, "
                        "ready to post.",
                        ["video-editing", "reels", "captions"],
                    ),
                    (
                        "I will edit your YouTube videos with pacing that keeps viewers watching",
                        "Cuts, captions, and a thumbnail-ready first three seconds.",
                        ["youtube", "video-editing", "pacing"],
                    ),
                    (
                        "I will create a 2D explainer animation for your product",
                        "Script to storyboard to final render — a video that explains what you do "
                        "in 60 seconds.",
                        ["2d-animation", "explainer-video", "motion-graphics"],
                    ),
                    (
                        "I will edit your wedding or event video into a highlight reel",
                        "The moments that matter, cut to music, delivered in days not months.",
                        ["wedding-video", "highlight-reel", "video-editing"],
                    ),
                    (
                        "I will add motion graphics and titles to your existing footage",
                        "Lower thirds, transitions, and titles that look intentional, not default.",
                        ["motion-graphics", "titles", "video-editing"],
                    ),
                    (
                        "I will color grade your footage to a cinematic look",
                        "Consistent, graded footage across every clip in your project.",
                        ["color-grading", "cinematic", "video-editing"],
                    ),
                    (
                        "I will create an animated logo intro for your videos",
                        "A 3-5 second sting that makes every upload feel like a channel, not a "
                        "folder.",
                        ["logo-animation", "motion-graphics", "branding"],
                    ),
                    (
                        "I will edit your podcast into video clips for social",
                        "Long-form audio or video cut into the clips that actually get shared.",
                        ["podcast", "clipping", "social-media"],
                    ),
                    (
                        "I will create a product demo video from screen recordings",
                        "Raw screen capture turned into a paced, narrated walkthrough.",
                        ["product-demo", "screen-recording", "video-editing"],
                    ),
                    (
                        "I will animate your static illustrations for social media",
                        "Subtle motion that makes a still image stop the scroll.",
                        ["animation", "social-media", "motion-graphics"],
                    ),
                    (
                        "I will edit real estate or property walkthrough videos",
                        "Steady, well-paced walkthroughs that make a listing feel larger.",
                        ["real-estate", "walkthrough", "video-editing"],
                    ),
                    (
                        "I will create looping animated backgrounds for streams or events",
                        "Seamless loops sized for your exact screen or stream layout.",
                        ["motion-graphics", "streaming", "animation"],
                    ),
                ],
            },
            "Marketing & Sales": {
                "seller": "marketer@skilrize.dev",
                "tiers": [
                    ("Basic", 10000, 5, 1),
                    ("Standard", 28000, 10, 2),
                    ("Premium", 75000, 21, 3),
                ],
                "questions": [
                    "What's the product or service, and who's the target customer?",
                    "What's already been tried, and what worked or didn't?",
                ],
                "gigs": [
                    (
                        "I will run and optimize your Meta and Google ad campaigns",
                        "Set up, tested, and optimized against a real cost-per-result target.",
                        ["meta-ads", "google-ads", "ppc"],
                    ),
                    (
                        "I will do keyword research and an on-page SEO audit",
                        "A prioritized list of exactly what to fix, not a 40-page report nobody "
                        "reads.",
                        ["seo", "keyword-research", "audit"],
                    ),
                    (
                        "I will build a 90-day content calendar for your brand",
                        "Platform-specific posts planned around what your audience actually "
                        "engages with.",
                        ["content-strategy", "social-media", "planning"],
                    ),
                    (
                        "I will set up email marketing automation in Mailchimp or Klaviyo",
                        "Welcome, abandoned-cart, and win-back flows, built and tested.",
                        ["email-marketing", "automation", "klaviyo"],
                    ),
                    (
                        "I will manage your Instagram and grow real engagement",
                        "Content, captions, and community management — no bot followers.",
                        ["instagram", "social-media", "community-management"],
                    ),
                    (
                        "I will write and set up a Google Ads search campaign",
                        "Keywords, ad copy, and conversion tracking configured from day one.",
                        ["google-ads", "ppc", "conversion-tracking"],
                    ),
                    (
                        "I will create a go-to-market plan for your product launch",
                        "Channels, timeline, and messaging — a plan you can actually execute.",
                        ["gtm-strategy", "product-launch", "marketing-strategy"],
                    ),
                    (
                        "I will audit your funnel and tell you where you're losing customers",
                        "A step-by-step look at your funnel with the leak points named.",
                        ["funnel-audit", "cro", "analytics"],
                    ),
                    (
                        "I will set up conversion tracking and analytics correctly",
                        "GA4, Meta Pixel, and conversion events — wired so your numbers are "
                        "trustworthy.",
                        ["ga4", "analytics", "tracking"],
                    ),
                    (
                        "I will write and design a lead magnet that actually converts",
                        "A guide or checklist built to trade for an email address, not ignored.",
                        ["lead-generation", "copywriting", "design"],
                    ),
                    (
                        "I will run influencer outreach for your product launch",
                        "Vetted micro-influencers in your niche, contacted and negotiated.",
                        ["influencer-marketing", "outreach", "product-launch"],
                    ),
                    (
                        "I will optimize your Amazon or Shopify product listings",
                        "Titles, images, and copy tuned for the platform's own search algorithm.",
                        ["amazon", "shopify", "listing-optimization"],
                    ),
                ],
            },
            "Data & Analytics": {
                "seller": "analyst@skilrize.dev",
                "tiers": [
                    ("Basic", 12000, 5, 1),
                    ("Standard", 38000, 10, 2),
                    ("Premium", 95000, 20, 3),
                ],
                "questions": [
                    "Where does the data live, and roughly how much is there?",
                    "What decision should this analysis help make?",
                ],
                "gigs": [
                    (
                        "I will build an interactive dashboard in Power BI or Tableau",
                        "Live-connected, not a static export — the numbers update themselves.",
                        ["power-bi", "tableau", "dashboards"],
                    ),
                    (
                        "I will clean and analyze your messy spreadsheet data",
                        "From a folder of exports to one clean, analyzable dataset.",
                        ["data-cleaning", "excel", "data-analysis"],
                    ),
                    (
                        "I will build a financial model for your startup",
                        "Revenue, costs, and runway — a model you can actually defend to an "
                        "investor.",
                        ["financial-modeling", "startup", "excel"],
                    ),
                    (
                        "I will write SQL queries and optimize your database performance",
                        "Queries that return in milliseconds, not the ten seconds you're used to.",
                        ["sql", "database", "performance"],
                    ),
                    (
                        "I will build a Python data pipeline to automate your reporting",
                        "A script that runs on schedule so nobody exports a CSV by hand again.",
                        ["python", "data-pipeline", "automation"],
                    ),
                    (
                        "I will train a machine learning model for your prediction task",
                        "From raw data to a validated model, with the accuracy numbers to "
                        "prove it.",
                        ["machine-learning", "python", "predictive-modeling"],
                    ),
                    (
                        "I will set up A/B testing and analyze the results properly",
                        "Correctly powered tests, analyzed for actual statistical significance.",
                        ["ab-testing", "statistics", "cro"],
                    ),
                    (
                        "I will build a customer segmentation analysis",
                        "Groups based on real behavior, not guesses — ready to target differently.",
                        ["segmentation", "data-analysis", "marketing-analytics"],
                    ),
                    (
                        "I will forecast your sales or demand using historical data",
                        "A model grounded in your own history, not an industry rule of thumb.",
                        ["forecasting", "data-analysis", "python"],
                    ),
                    (
                        "I will build an ETL pipeline connecting your tools together",
                        "Your CRM, spreadsheet, and database, kept in sync automatically.",
                        ["etl", "data-engineering", "automation"],
                    ),
                    (
                        "I will audit and fix your existing Excel or Google Sheets model",
                        "The same spreadsheet, minus the broken formulas and circular references.",
                        ["excel", "google-sheets", "audit"],
                    ),
                    (
                        "I will build a real-time analytics dashboard for your app",
                        "Usage, retention, and funnel metrics, visible the moment they happen.",
                        ["dashboards", "product-analytics", "real-time"],
                    ),
                ],
            },
            "Business & Admin": {
                "seller": "va@skilrize.dev",
                "tiers": [
                    ("Basic", 6000, 5, 1),
                    ("Standard", 18000, 14, 2),
                    ("Premium", 42000, 30, 3),
                ],
                "questions": [
                    "What does a typical week of this work look like?",
                    "Which tools do you already use (calendar, CRM, accounting)?",
                ],
                "gigs": [
                    (
                        "I will be your virtual assistant for inbox and calendar management",
                        "Your inbox at zero, your calendar conflict-free, every week.",
                        ["virtual-assistant", "inbox-management", "scheduling"],
                    ),
                    (
                        "I will set up and manage your bookkeeping in QuickBooks",
                        "Categorized transactions and monthly reports, reconciled and accurate.",
                        ["bookkeeping", "quickbooks", "accounting"],
                    ),
                    (
                        "I will manage your project in Asana, Trello, or ClickUp",
                        "Boards, timelines, and status updates kept current so nothing slips.",
                        ["project-management", "asana", "clickup"],
                    ),
                    (
                        "I will handle customer support tickets for your business",
                        "Timely, on-brand responses across email or chat, with a weekly summary.",
                        ["customer-support", "helpdesk", "virtual-assistant"],
                    ),
                    (
                        "I will research and build a list of qualified sales leads",
                        "Verified contacts matching your exact ideal customer profile.",
                        ["lead-generation", "research", "sales"],
                    ),
                    (
                        "I will prepare and file your business's tax documents",
                        "Organized, accurate filings — done by someone who checks the details "
                        "twice.",
                        ["tax-preparation", "accounting", "compliance"],
                    ),
                    (
                        "I will set up your CRM and import your existing contacts",
                        "A working pipeline, not just a spreadsheet renamed 'CRM'.",
                        ["crm", "sales-ops", "data-migration"],
                    ),
                    (
                        "I will manage vendor relationships and procurement for your business",
                        "Quotes compared, orders placed, and deliveries tracked, so you don't "
                        "have to.",
                        ["procurement", "vendor-management", "operations"],
                    ),
                    (
                        "I will create SOPs and process documentation for your team",
                        "Step-by-step guides so a new hire doesn't have to ask you everything.",
                        ["sop", "process-documentation", "operations"],
                    ),
                    (
                        "I will handle recruitment screening and interview scheduling",
                        "Resumes screened against your criteria, interviews booked without the "
                        "back-and-forth.",
                        ["recruitment", "hr", "scheduling"],
                    ),
                    (
                        "I will manage your online store's order fulfillment",
                        "Orders processed, tracked, and customers updated, every single day.",
                        ["order-fulfillment", "ecommerce", "operations"],
                    ),
                    (
                        "I will prepare board-ready financial and operations reports",
                        "The numbers your board actually asks for, formatted the way they expect.",
                        ["reporting", "finance", "operations"],
                    ),
                ],
            },
            "Academic Support": {
                "seller": "tutor@skilrize.dev",
                "tiers": [
                    ("Basic", 2500, 2, 1),
                    ("Standard", 9000, 5, 2),
                    ("Premium", 22000, 10, 3),
                ],
                "questions": [
                    "What's the subject, level, and specific topic?",
                    "When's this needed by, and is there a syllabus to follow?",
                ],
                "gigs": [
                    (
                        "I will tutor you in calculus, algebra, or statistics",
                        "One-on-one sessions that build the intuition, not just the answer.",
                        ["math-tutoring", "calculus", "statistics"],
                    ),
                    (
                        "I will help you prepare for the SAT or GRE",
                        "A study plan built around your actual weak sections, not a generic "
                        "course.",
                        ["sat-prep", "gre-prep", "test-prep"],
                    ),
                    (
                        "I will proofread and give feedback on your university essay",
                        "Structure, argument, and grammar — feedback you can act on before the "
                        "deadline.",
                        ["essay-editing", "proofreading", "academic-writing"],
                    ),
                    (
                        "I will help you understand and debug your programming assignment",
                        "I explain the why, not just hand you working code.",
                        ["programming-help", "tutoring", "debugging"],
                    ),
                    (
                        "I will conduct literature reviews for your research paper",
                        "Relevant sources found, summarized, and cited in your required format.",
                        ["literature-review", "research", "citations"],
                    ),
                    (
                        "I will tutor you in accounting or financial statement analysis",
                        "Balance sheets and ratios explained until they actually make sense.",
                        ["accounting-tutoring", "finance", "tutoring"],
                    ),
                    (
                        "I will help you build and rehearse your thesis defense presentation",
                        "Slides and a rehearsed narrative that anticipates the committee's "
                        "questions.",
                        ["thesis-defense", "presentation", "coaching"],
                    ),
                    (
                        "I will create study notes and flashcards for your exam",
                        "Condensed, exam-focused notes from your textbook or lecture slides.",
                        ["study-notes", "flashcards", "exam-prep"],
                    ),
                    (
                        "I will tutor you in a foreign language for conversational fluency",
                        "Real conversation practice, not just vocabulary drills.",
                        ["language-tutoring", "conversation-practice", "fluency"],
                    ),
                    (
                        "I will help you with data analysis for your research project",
                        "Statistical tests run correctly and explained in plain language.",
                        ["research-methods", "statistics", "data-analysis"],
                    ),
                    (
                        "I will edit and format your dissertation to university spec",
                        "Formatting, citations, and structure checked against your "
                        "university's exact guidelines.",
                        ["dissertation-editing", "formatting", "citations"],
                    ),
                    (
                        "I will tutor you in physics or chemistry for high school or college",
                        "Concepts explained with the intuition your textbook skips.",
                        ["physics-tutoring", "chemistry-tutoring", "science"],
                    ),
                ],
            },
        }

        with use_scope(GLOBAL_SCOPE):
            for category_name, spec in catalog.items():
                seller = User.objects.filter(email=spec["seller"]).first()
                if seller is None:
                    continue
                category = Category.objects.filter(name=category_name, parent=None).first()
                requirements = [
                    {"key": f"req_{index + 1}", "label": question, "required": True}
                    for index, question in enumerate(spec["questions"])
                ]

                for title, description, tags in spec["gigs"]:
                    if Gig.objects.filter(title=title).exists():
                        continue

                    gig = Gig.objects.create(
                        seller=seller,
                        title=title,
                        description=description,
                        category=category,
                        tags=tags,
                        requirements=requirements,
                    )
                    for tier_name, (name, price, days, revisions) in zip(
                        ["basic", "standard", "premium"], spec["tiers"], strict=True
                    ):
                        Package.objects.create(
                            gig=gig,
                            tier=tier_name,
                            name=name,
                            price=Decimal(price),
                            delivery_days=days,
                            revisions=revisions,
                            features=[f"{revisions} revision(s)", f"{days}-day delivery"],
                        )
                    gig.publish()

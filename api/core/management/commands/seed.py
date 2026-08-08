"""
Seed the category and skill taxonomy, and optionally a demo dataset.

    python manage.py seed             # taxonomy only — safe on any environment
    python manage.py seed --demo      # plus sample users, briefs, and a contract

The taxonomy is real reference data the product needs in every environment.
The demo flag is for local work only and refuses to run outside DEBUG, because
seeding fake users into production is exactly the kind of thing that happens
once and is never fully cleaned up.
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
        if not settings.DEBUG:
            raise CommandError("Refusing to seed demo data outside DEBUG.")

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
        """A starter catalogue, so the browse grid is not empty on first run."""
        from accounts.models import User
        from gigs.models import Gig, GigExtra, Package
        from marketplace.models import Category

        listings = [
            (
                "designer@skilrize.dev",
                "I will design a complete brand identity for your startup",
                "You get a primary logo, a secondary mark, a colour system, type choices, and a "
                "one-page usage guide. I work in two rounds: three directions first, then we "
                "refine the one you pick.",
                "Design & Creative",
                ["logo", "branding", "identity"],
                [
                    ("Logo only", 8000, 3, 1),
                    ("Logo + palette", 15000, 5, 2),
                    ("Full identity", 30000, 8, 4),
                ],
                [("Source files", 3000, 0), ("48-hour delivery", 5000, -2)],
                [
                    "What is the brand called, and who is it for?",
                    "Share two brands whose look you admire, and say why.",
                ],
            ),
            (
                "dev@skilrize.dev",
                "I will build a responsive web app in React and Django",
                "A production-ready build: typed front end, REST API, Postgres, auth, and a "
                "deploy pipeline. Fixed scope, fixed price, no surprises.",
                "Development & IT",
                ["react", "django", "fullstack"],
                [
                    ("Landing page", 25000, 5, 1),
                    ("Web app (5 screens)", 90000, 14, 2),
                    ("Full product build", 220000, 30, 3),
                ],
                [("Deployment setup", 12000, 2)],
                [
                    "What should the app do, in plain language?",
                    "Do you have designs already, or do you need those too?",
                ],
            ),
            (
                "dev@skilrize.dev",
                "I will write clean technical documentation for your API",
                "Reference docs, a getting-started guide, and runnable examples. I read the code "
                "rather than guessing from the endpoint names.",
                "Writing & Translation",
                ["documentation", "api", "technical writing"],
                [("Single endpoint set", 6000, 3, 2), ("Full API reference", 22000, 10, 3)],
                [],
                ["Where is the code or the OpenAPI spec?"],
            ),
            (
                "designer@skilrize.dev",
                "I will edit your short-form video for social",
                "Cuts, captions, colour, and sound. Delivered in vertical and square, ready to "
                "post.",
                "Video & Animation",
                ["video editing", "reels", "captions"],
                [("Up to 60 seconds", 4500, 2, 2), ("Up to 3 minutes", 11000, 4, 3)],
                [("Extra platform crop", 1500, 0)],
                ["Link the raw footage.", "What is the hook in the first three seconds?"],
            ),
        ]

        with use_scope(GLOBAL_SCOPE):
            for email, title, description, category, tags, tiers, extras, questions in listings:
                if Gig.objects.filter(title=title).exists():
                    continue
                seller = User.objects.filter(email=email).first()
                if seller is None:
                    continue

                gig = Gig.objects.create(
                    seller=seller,
                    title=title,
                    description=description,
                    category=Category.objects.filter(name=category, parent=None).first(),
                    tags=tags,
                    requirements=[
                        {"key": f"req_{index + 1}", "label": question, "required": True}
                        for index, question in enumerate(questions)
                    ],
                )
                for tier_name, (name, price, days, revisions) in zip(
                    ["basic", "standard", "premium"], tiers, strict=False
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
                for extra_title, extra_price, extra_days in extras:
                    GigExtra.objects.create(
                        gig=gig,
                        title=extra_title,
                        price=Decimal(extra_price),
                        extra_days=extra_days,
                    )
                gig.publish()

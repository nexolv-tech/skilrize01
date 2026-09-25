"""
List NEXOLV.TECH's own services as the platform's first seller.

    python manage.py create_storefront --email owner@example.com

SkilRize is operated by NEXOLV.TECH, a software studio. Before any outside
freelancer has joined, the catalogue would otherwise be empty — which is what
the payment gateway's reviewers found when they tried to follow a service
through to checkout. These are the studio's real services, sold by the real
operator, so nothing here is invented traction: the listings say who sells
them.

Idempotent: re-running skips services that already exist. Prices and package
contents are a starting point for the owner to review and edit from the
dashboard — they are ordinary listings, not fixtures.

The account is created without a usable password and is **not** marked as
verified. The owner sets a password through "Forgot password" and verifies
email, phone and identity exactly as any other seller does before they can
take orders out of escrow.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.scope import GLOBAL_SCOPE, use_scope

SERVICES = [
    {
        "category": "Development & IT",
        "title": "I will build a fast, mobile-friendly website for your business",
        "description": (
            "A complete business website built with Next.js: designed around your content, "
            "fast on mobile networks, and set up so you can edit it yourself. Includes contact "
            "forms, on-page SEO and deployment to your own domain. You receive the full source "
            "code.\n\nWe start with a short call about your business and the people the site is "
            "for, share a first design within the first few days, and build once you approve it."
        ),
        "tags": ["website", "nextjs", "business website"],
        "requirements": [
            ("business", "What does your business do, and who is the website for?", True),
            ("pages", "Which pages do you need? (e.g. Home, Services, About, Contact)", True),
            ("brand", "Do you have a logo, brand colours or sites you like? Share links.", False),
        ],
        "faq": [
            (
                "Can I update the content myself?",
                "Yes. Every package includes a simple way to change text and images without "
                "touching code, plus a short walkthrough video.",
            ),
            (
                "Do you provide hosting?",
                "We deploy to hosting you own, so the site is always yours. Most business sites "
                "run on a free tier; we recommend a setup if you have none.",
            ),
            (
                "What if I want changes after delivery?",
                "The revisions in your package cover changes to what was agreed. New pages or "
                "features after delivery are quoted separately.",
            ),
        ],
        "packages": [
            (
                "Starter site",
                "A clean site to get your business found.",
                35000,
                7,
                2,
                [
                    "Up to 5 pages",
                    "Mobile-responsive design",
                    "Contact form",
                    "On-page SEO setup",
                    "Deployment to your domain",
                ],
            ),
            (
                "Business site",
                "A site your team can run day to day.",
                75000,
                14,
                3,
                [
                    "Up to 10 pages",
                    "Editable content (CMS)",
                    "Blog or news section",
                    "WhatsApp chat button",
                    "Analytics setup",
                    "Deployment to your domain",
                ],
            ),
            (
                "Custom web platform",
                "Accounts, bookings or a workflow built in.",
                150000,
                30,
                5,
                [
                    "Up to 20 pages",
                    "User accounts or booking system",
                    "Admin dashboard",
                    "Enquiry or order workflow",
                    "Performance and SEO audit",
                    "30 days of post-launch support",
                ],
            ),
        ],
        "extras": [("Urdu version of the site", 15000, 5)],
    },
    {
        "category": "Development & IT",
        "title": "I will develop an Android and iOS app for your business",
        "description": (
            "One app for Android and iOS, built with Flutter from a single codebase. We design "
            "the screens with you first, build against your existing system or set up a new "
            "backend, and prepare the store submissions. You receive the source code and a "
            "handover call with your team."
        ),
        "tags": ["mobile app", "flutter", "android", "ios"],
        "requirements": [
            ("purpose", "What should the app let people do? Describe the main tasks.", True),
            ("existing", "Do you already have a backend, website or designs?", True),
            ("platforms", "Which platforms do you need first: Android, iOS or both?", True),
        ],
        "faq": [
            (
                "Do you publish the app to the stores?",
                "We submit it from your own developer accounts, so you own the listing. Google "
                "charges a one-time fee and Apple a yearly one; we guide you through both.",
            ),
            (
                "Can the app connect to the system I already use?",
                "Usually, yes — if it has an API or a database we can reach. Tell us what you "
                "use and we confirm before any work starts.",
            ),
        ],
        "packages": [
            (
                "App prototype",
                "A working Android build to test the idea.",
                90000,
                14,
                2,
                [
                    "Up to 6 screens",
                    "Installable Android build",
                    "Your branding and colours",
                    "Source code",
                ],
            ),
            (
                "Launch-ready app",
                "Android and iOS, ready for real users.",
                180000,
                30,
                3,
                [
                    "Up to 15 screens",
                    "Android and iOS builds",
                    "Login and user accounts",
                    "Push notifications",
                    "Play Store submission",
                ],
            ),
            (
                "Full product",
                "App, backend and admin panel together.",
                350000,
                60,
                5,
                [
                    "Up to 30 screens",
                    "Android and iOS builds",
                    "Backend API and admin panel",
                    "Payments or bookings",
                    "Play Store and App Store submission",
                    "60 days of bug-fix support",
                ],
            ),
        ],
        "extras": [("Admin web panel", 60000, 10)],
    },
    {
        "category": "Development & IT",
        "title": "I will automate your business workflows with AI",
        "description": (
            "Hand repetitive work to software: chatbots that answer customer questions on "
            "WhatsApp or your website from your own information, automatic data entry between "
            "your forms, sheets and CRM, and AI-drafted replies and reports your team approves "
            "before they go out.\n\nWe map the process with you first, then build, test and "
            "document it, so your team knows exactly what runs and when."
        ),
        "tags": ["automation", "ai", "chatbot", "whatsapp"],
        "requirements": [
            (
                "task",
                "Which task takes your team the most time? Walk us through it step by step.",
                True,
            ),
            ("tools", "Which tools does it involve? (e.g. WhatsApp, Sheets, Gmail, a CRM)", True),
            ("volume", "Roughly how often does it happen — per day or per week?", False),
        ],
        "faq": [
            (
                "Is my business data safe?",
                "Automations run on accounts you own, and we ask only for the access each "
                "workflow needs. We keep no copies of your data after handover.",
            ),
            (
                "What does it cost to run afterwards?",
                "Most workflows run on free tiers. Where an AI service charges per use, we "
                "estimate the monthly cost before we build anything.",
            ),
        ],
        "packages": [
            (
                "Single workflow",
                "One repetitive task, handled automatically.",
                25000,
                5,
                2,
                [
                    "One automated workflow",
                    "Up to 3 connected tools",
                    "Set up on your own accounts",
                    "Written documentation",
                ],
            ),
            (
                "Chatbot or multi-step flow",
                "A bot that answers from your own information.",
                60000,
                12,
                3,
                [
                    "WhatsApp or website chatbot",
                    "Answers from your FAQs and documents",
                    "Hands over to a person when needed",
                    "Up to 5 connected tools",
                    "Written documentation",
                ],
            ),
            (
                "Automation package",
                "Several workflows and an assistant for your team.",
                120000,
                25,
                4,
                [
                    "Up to 4 workflows or bots",
                    "AI assistant for your team",
                    "Log of what ran and when",
                    "Staff training session",
                    "30 days of monitoring",
                ],
            ),
        ],
        "extras": [("First month of maintenance", 15000, 0)],
    },
    {
        "category": "Design & Creative",
        "title": "I will design a clear UI/UX for your website or app",
        "description": (
            "Screens your users understand the first time. We start from who uses the product "
            "and what they need to get done, then deliver wireframes, polished designs in Figma "
            "and a clickable prototype your developers can build from."
        ),
        "tags": ["ui design", "ux design", "figma"],
        "requirements": [
            ("product", "What is the product, and who uses it?", True),
            ("brand", "Do you have brand guidelines, a logo or colours?", False),
            ("references", "Share links to apps or sites whose feel you like.", False),
        ],
        "faq": [
            (
                "Will I get the Figma file?",
                "Yes — the full file, organised with named layers and reusable components.",
            ),
            (
                "Can you work with my developers?",
                "Designs are handed over with spacing, colours and states documented, and we "
                "answer your developers' questions during the build.",
            ),
        ],
        "packages": [
            (
                "Key screens",
                "The screens that matter most.",
                20000,
                5,
                2,
                ["Up to 5 screens", "Mobile or desktop layout", "Figma source file"],
            ),
            (
                "Complete flow",
                "A full user journey, prototyped.",
                45000,
                10,
                3,
                [
                    "Up to 15 screens",
                    "Mobile and desktop layouts",
                    "Clickable prototype",
                    "Figma source file",
                ],
            ),
            (
                "Design system",
                "Everything your product needs to scale.",
                90000,
                20,
                4,
                [
                    "Up to 30 screens",
                    "Reusable component library",
                    "Clickable prototype",
                    "Developer handover notes",
                    "Figma source file",
                ],
            ),
        ],
        "extras": [("Logo design", 12000, 3)],
    },
]


class Command(BaseCommand):
    help = "List NEXOLV.TECH's own services as the first seller on the platform."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="The studio's seller account email.")
        parser.add_argument("--name", default="NEXOLV.TECH", help="Public display name.")

    @transaction.atomic
    def handle(self, *args, **options):
        from accounts.models import BuyerProfile, SellerProfile, User
        from gigs.models import Gig, GigExtra, Package
        from marketplace.models import Category

        email = options["email"].strip().lower()
        seller, created = User.objects.get_or_create(
            email=email,
            defaults={
                "handle": "nexolv-tech",
                "full_name": options["name"],
                "headline": "Software studio · websites, mobile apps, AI automation and UI/UX",
                "bio": (
                    "NEXOLV.TECH is the software studio that builds and operates SkilRize. "
                    "Based in Rawalpindi, Pakistan."
                ),
                "country": "PK",
                "city": "Rawalpindi",
            },
        )
        if created:
            seller.set_unusable_password()
            seller.save()
        SellerProfile.objects.get_or_create(user=seller)
        BuyerProfile.objects.get_or_create(user=seller)

        made = 0
        with use_scope(GLOBAL_SCOPE):
            for spec in SERVICES:
                if Gig.objects.filter(seller=seller, title=spec["title"]).exists():
                    continue
                category = Category.objects.filter(name=spec["category"], parent=None).first()
                if category is None:
                    raise CommandError("The taxonomy is missing — run `manage.py seed` first.")

                gig = Gig.objects.create(
                    seller=seller,
                    title=spec["title"],
                    description=spec["description"],
                    category=category,
                    tags=spec["tags"],
                    requirements=[
                        {"key": key, "label": label, "required": required}
                        for key, label, required in spec["requirements"]
                    ],
                    faq=[{"question": q, "answer": a} for q, a in spec["faq"]],
                )
                for tier, (name, blurb, price, days, revisions, features) in zip(
                    ["basic", "standard", "premium"], spec["packages"], strict=True
                ):
                    Package.objects.create(
                        gig=gig,
                        tier=tier,
                        name=name,
                        description=blurb,
                        price=Decimal(price),
                        delivery_days=days,
                        revisions=revisions,
                        features=features,
                    )
                for title, price, days in spec["extras"]:
                    GigExtra.objects.create(
                        gig=gig, title=title, price=Decimal(price), extra_days=days
                    )
                gig.publish()
                made += 1

        self.stdout.write(
            self.style.SUCCESS(f"Storefront ready: {made} service(s) listed for {email}.")
        )
        if created:
            self.stdout.write(
                f"The account has no password yet. Set one with “Forgot password” for {email}, "
                "then finish verification from the dashboard."
            )

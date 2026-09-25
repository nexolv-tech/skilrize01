"""
Give an existing account an admin role, or take it away.

    python manage.py set_admin_role owner@example.com super_admin
    python manage.py set_admin_role someone@example.com none

The first Super Admin has to come from here: the console only lets a Super
Admin grant roles. The account must already exist (sign up normally
first); its sessions are ended so the next sign-in asks for the
authenticator every admin role requires.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from accounts import auth as tokens
from accounts.models import User
from core.models import AuditLog


class Command(BaseCommand):
    help = "Set an account's admin role (super_admin, finance_admin, moderator, …, or none)."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("role", help=", ".join(r or "none" for r in User.AdminRole.values))

    def handle(self, *args, email: str, role: str, **options):
        role = "" if role == "none" else role
        if role not in User.AdminRole.values:
            raise CommandError(
                f"Unknown role {role!r}. Choose one of: "
                + ", ".join(r or "none" for r in User.AdminRole.values)
            )
        user = User.objects.filter(email__iexact=email.strip()).first()
        if user is None:
            raise CommandError(f"No account uses {email}. Sign up with it first.")

        before = user.admin_role
        user.admin_role = role
        user.save(update_fields=["admin_role", "updated_at"])
        tokens.revoke_all(user, reason="admin role set from the command line")
        AuditLog.record(
            action=AuditLog.Action.UPDATE,
            target=user,
            before={"admin_role": before},
            after={"admin_role": role},
            justification="Admin role set with manage.py set_admin_role.",
        )
        label = User.AdminRole(role).label if role else "no admin role"
        self.stdout.write(
            self.style.SUCCESS(
                f"{user.email} now has {label}. Their sessions were ended; the next sign-in "
                "asks them to set up an authenticator app."
            )
        )

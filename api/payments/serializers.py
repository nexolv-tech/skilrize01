from __future__ import annotations

from rest_framework import serializers

from .models import Payout, PayoutProfile


class PayoutProfileSerializer(serializers.ModelSerializer):
    """The freelancer's own view — `account_number` and `cnic` are
    write-only. Nothing reads an `EncryptedTextField` back through the API;
    the point of encrypting them at rest is defeated if the API then
    echoes them in plaintext on every GET."""

    is_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = PayoutProfile
        fields = [
            "bank_code",
            "bank_name",
            "account_number",
            "verified_account_title",
            "cnic",
            "msisdn",
            "is_complete",
        ]
        read_only_fields = ["verified_account_title", "is_complete"]
        extra_kwargs = {
            "account_number": {"write_only": True},
            "cnic": {"write_only": True},
        }


class PayoutSerializer(serializers.ModelSerializer):
    milestone_title = serializers.CharField(source="milestone.title", read_only=True)
    contract_id = serializers.IntegerField(source="milestone.contract_id", read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "milestone_title",
            "contract_id",
            "amount",
            "currency",
            "status",
            "failure_reason",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields

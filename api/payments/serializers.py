from __future__ import annotations

from rest_framework import serializers

from . import institutions
from .models import Payout, PayoutProfile, Refund


class PayoutProfileSerializer(serializers.ModelSerializer):
    """The freelancer's own view — `account_number` and `cnic` are
    write-only. Nothing reads an `EncryptedTextField` back through the API;
    the point of encrypting them at rest is defeated if the API then
    echoes them in plaintext on every GET."""

    is_complete = serializers.BooleanField(read_only=True)
    swich_ready = serializers.BooleanField(read_only=True)

    class Meta:
        model = PayoutProfile
        fields = [
            "bank_code",
            "bank_name",
            "account_title",
            "account_number",
            "cnic",
            "msisdn",
            "is_complete",
            "swich_ready",
        ]
        read_only_fields = ["is_complete", "swich_ready"]
        extra_kwargs = {
            "account_number": {"write_only": True},
            "cnic": {"write_only": True},
        }

    def validate_bank_code(self, value: str) -> str:
        value = (value or "").strip().upper()
        if value and value not in institutions.BY_CODE:
            raise serializers.ValidationError("Choose a bank or wallet from the list.")
        return value

    def validate(self, attrs):
        # A listed bank or wallet names itself, so the name always matches
        # the code Swich is sent (D56).
        code = attrs.get("bank_code")
        if code:
            attrs["bank_name"] = institutions.name_of(code)
        elif code == "" and "bank_name" not in attrs:
            attrs["bank_name"] = ""
        return attrs


class PayoutSerializer(serializers.ModelSerializer):
    milestone_title = serializers.CharField(source="milestone.title", read_only=True)
    contract_id = serializers.IntegerField(source="milestone.contract_id", read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "milestone_title",
            "contract_id",
            "gross_amount",
            "commission_percent",
            "commission_amount",
            "net_amount",
            "currency",
            "status",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    milestone_title = serializers.CharField(source="milestone.title", read_only=True)
    contract_id = serializers.IntegerField(source="milestone.contract_id", read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id",
            "milestone_title",
            "contract_id",
            "amount",
            "currency",
            "reason",
            "status",
            "refunded_at",
            "created_at",
        ]
        read_only_fields = fields

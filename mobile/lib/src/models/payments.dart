/// Phase 3 (D41) — escrow payments via Swich. `PayoutProfile` never carries
/// `account_number`/`cnic`: the API is write-only on those fields, so there
/// is nothing here to decode back even if a response somehow included them.
library;

class PayoutProfile {
  PayoutProfile({
    required this.bankCode,
    required this.bankName,
    required this.verifiedAccountTitle,
    required this.msisdn,
    required this.isComplete,
  });

  final String bankCode;
  final String bankName;
  final String verifiedAccountTitle;
  final String msisdn;
  final bool isComplete;

  factory PayoutProfile.fromJson(Map<String, dynamic> json) => PayoutProfile(
        bankCode: json['bank_code'] as String? ?? '',
        bankName: json['bank_name'] as String? ?? '',
        verifiedAccountTitle: json['verified_account_title'] as String? ?? '',
        msisdn: json['msisdn'] as String? ?? '',
        isComplete: json['is_complete'] as bool? ?? false,
      );
}

class Payout {
  Payout({
    required this.id,
    required this.milestoneTitle,
    required this.contractId,
    required this.amount,
    required this.currency,
    required this.status,
    required this.failureReason,
    required this.createdAt,
  });

  final int id;
  final String milestoneTitle;
  final int contractId;
  final String amount;
  final String currency;
  final String status;
  final String failureReason;
  final DateTime createdAt;

  factory Payout.fromJson(Map<String, dynamic> json) => Payout(
        id: json['id'] as int,
        milestoneTitle: json['milestone_title'] as String? ?? '',
        contractId: json['contract_id'] as int? ?? 0,
        amount: '${json['amount'] ?? '0'}',
        currency: json['currency'] as String? ?? 'PKR',
        status: json['status'] as String? ?? 'pending',
        failureReason: json['failure_reason'] as String? ?? '',
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}

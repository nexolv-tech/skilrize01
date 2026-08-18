/// Phase 3 (D42) — custodial escrow, no payment gateway. `PayoutProfile`
/// never carries `account_number`/`cnic`: the API is write-only on those
/// fields, so there is nothing here to decode back even if a response
/// somehow included them.
library;

class BankTransferInstructions {
  BankTransferInstructions({
    required this.bankName,
    required this.accountTitle,
    required this.accountNumber,
    required this.commissionPercent,
  });

  final String bankName;
  final String accountTitle;
  final String accountNumber;
  final String commissionPercent;

  factory BankTransferInstructions.fromJson(Map<String, dynamic> json) =>
      BankTransferInstructions(
        bankName: json['bank_name'] as String? ?? '',
        accountTitle: json['account_title'] as String? ?? '',
        accountNumber: json['account_number'] as String? ?? '',
        commissionPercent: '${json['commission_percent'] ?? '0'}',
      );
}

class PayoutProfile {
  PayoutProfile({
    required this.bankName,
    required this.accountTitle,
    required this.msisdn,
    required this.isComplete,
  });

  final String bankName;
  final String accountTitle;
  final String msisdn;
  final bool isComplete;

  factory PayoutProfile.fromJson(Map<String, dynamic> json) => PayoutProfile(
        bankName: json['bank_name'] as String? ?? '',
        accountTitle: json['account_title'] as String? ?? '',
        msisdn: json['msisdn'] as String? ?? '',
        isComplete: json['is_complete'] as bool? ?? false,
      );
}

class Payout {
  Payout({
    required this.id,
    required this.milestoneTitle,
    required this.contractId,
    required this.grossAmount,
    required this.commissionPercent,
    required this.commissionAmount,
    required this.netAmount,
    required this.currency,
    required this.status,
    required this.createdAt,
  });

  final int id;
  final String milestoneTitle;
  final int contractId;
  final String grossAmount;
  final String commissionPercent;
  final String commissionAmount;
  final String netAmount;
  final String currency;
  final String status;
  final DateTime createdAt;

  factory Payout.fromJson(Map<String, dynamic> json) => Payout(
        id: json['id'] as int,
        milestoneTitle: json['milestone_title'] as String? ?? '',
        contractId: json['contract_id'] as int? ?? 0,
        grossAmount: '${json['gross_amount'] ?? '0'}',
        commissionPercent: '${json['commission_percent'] ?? '0'}',
        commissionAmount: '${json['commission_amount'] ?? '0'}',
        netAmount: '${json['net_amount'] ?? '0'}',
        currency: json['currency'] as String? ?? 'PKR',
        status: json['status'] as String? ?? 'pending',
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}

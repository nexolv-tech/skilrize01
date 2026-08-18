import 'package:flutter/material.dart';

import '../state/session.dart';

/// Escrow funding UI — the platform's own bank account, shown before a
/// client confirms they've paid (Phase 3, D42). Shared between the
/// contract-milestone flow and the gig-order flow, which both fund the
/// same way: a real bank transfer this app cannot verify, followed by the
/// client's own confirmation.
///
/// Returns the reference note the client typed if they confirmed, or
/// `null` if they cancelled — callers pass whichever they get straight to
/// `fundMilestone`/`orderGig`.
Future<String?> showBankTransferDialog(
  BuildContext context, {
  required Session session,
  required String amount,
}) {
  final reference = TextEditingController();
  return showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Fund into escrow'),
      content: SizedBox(
        width: 360,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Transfer Rs $amount to this account, then confirm below.'),
            const SizedBox(height: 12),
            FutureBuilder(
              future: session.api.bankTransferInstructions(),
              builder: (context, snapshot) {
                final data = snapshot.data;
                if (data == null) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _row('Bank', data.bankName),
                    _row('Account title', data.accountTitle),
                    _row('Account number', data.accountNumber),
                  ],
                );
              },
            ),
            const SizedBox(height: 12),
            TextField(
              controller: reference,
              decoration: const InputDecoration(
                labelText: 'Transfer reference (optional)',
                hintText: 'Bank transaction ID, for reconciliation',
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, reference.text.trim()),
          child: const Text("I've sent the payment"),
        ),
      ],
    ),
  );
}

Widget _row(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12.5, color: Colors.grey)),
          Flexible(
            child: Text(value, textAlign: TextAlign.end, style: const TextStyle(fontSize: 12.5)),
          ),
        ],
      ),
    );

/// What a client sees before releasing a milestone — the platform's
/// commission split out, so "release" doesn't read as though the
/// freelancer gets the full amount.
class ReleaseEstimate extends StatelessWidget {
  const ReleaseEstimate({super.key, required this.session, required this.amount});
  final Session session;
  final String amount;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder(
      future: session.api.bankTransferInstructions(),
      builder: (context, snapshot) {
        final data = snapshot.data;
        if (data == null) return const SizedBox.shrink();
        final commission = double.tryParse(data.commissionPercent) ?? 0;
        final net = (double.tryParse(amount) ?? 0) * (1 - commission / 100);
        return Text(
          'The freelancer receives Rs ${net.toStringAsFixed(2)} (Rs $amount minus our '
          '${data.commissionPercent}% fee).',
          style: const TextStyle(fontSize: 12, color: Colors.grey),
        );
      },
    );
  }
}

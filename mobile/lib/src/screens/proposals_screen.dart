import 'package:flutter/material.dart';

import '../models/marketplace.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

/// A freelancer's own proposals, with withdraw and trial status.
class ProposalsScreen extends StatelessWidget {
  const ProposalsScreen({super.key, required this.session});

  final Session session;

  @override
  Widget build(BuildContext context) {
    final key = GlobalKey<AsyncListState<Proposal>>();
    return Scaffold(
      appBar: AppBar(title: const Text('Your proposals')),
      body: AsyncList<Proposal>(
        key: key,
        loader: () async => (await session.api.myProposals()).results,
        emptyIcon: Icons.send_outlined,
        emptyText: "You haven't submitted any proposals yet.",
        itemBuilder: (context, proposal) {
          final scheme = Theme.of(context).colorScheme;
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(proposal.projectTitle,
                            style: Theme.of(context).textTheme.titleMedium),
                      ),
                      StatusPill(proposal.status),
                    ],
                  ),
                  const SizedBox(height: 6),
                  if (proposal.bidAmount != null)
                    Text('Rs ${proposal.bidAmount}', style: Theme.of(context).textTheme.bodyMedium),
                  if (proposal.trial != null) ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: scheme.tertiaryContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Trial: ${proposal.trial!.status} · Rs ${proposal.trial!.amount}',
                        style: TextStyle(color: scheme.onTertiaryContainer, fontSize: 12),
                      ),
                    ),
                  ],
                  if (proposal.isEditable) ...[
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: () async {
                          await session.api.withdrawProposal(proposal.id);
                          key.currentState?.reload();
                        },
                        child: const Text('Withdraw'),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

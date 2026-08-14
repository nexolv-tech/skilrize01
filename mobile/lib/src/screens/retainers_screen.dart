import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/professional.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';
import '../widgets/money_gate.dart';

/// Browse + subscribe to retainers — mirrors `web/app/(app)/retainers`.
/// Subscribing captures recurring funds, so it goes through the same
/// [MoneyGateBanner] treatment as gig ordering, even though the underlying
/// refusal here is more often plan-entitlement (`upgrade_required`) than the
/// `CanMoveMoney` codes.
class RetainersScreen extends StatefulWidget {
  const RetainersScreen({super.key, required this.session});
  final Session session;

  @override
  State<RetainersScreen> createState() => _RetainersScreenState();
}

class _RetainersScreenState extends State<RetainersScreen> {
  ApiError? _error;
  int? _busyId;

  Future<void> _subscribe(Retainer retainer) async {
    setState(() {
      _busyId = retainer.id;
      _error = null;
    });
    try {
      await widget.session.api.subscribeToRetainer(retainer.id);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Subscribed to retainer.')));
      }
    } on ApiError catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busyId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Retainers')),
      body: Column(
        children: [
          if (_error != null)
            Padding(padding: const EdgeInsets.all(12), child: MoneyGateBanner(error: _error!)),
          Expanded(
            child: AsyncList<Retainer>(
              loader: () async => (await widget.session.api.retainers()).results,
              emptyIcon: Icons.repeat_outlined,
              emptyText: 'No retainers listed yet.',
              itemBuilder: (context, retainer) => Card(
                margin: const EdgeInsets.only(bottom: 10),
                child: ListTile(
                  title: Text(retainer.title),
                  subtitle: Text('${retainer.sellerName} · Rs ${retainer.monthlyPrice}/mo'),
                  trailing: FilledButton.tonal(
                    onPressed: _busyId != null ? null : () => _subscribe(retainer),
                    child: Text(_busyId == retainer.id ? 'Working…' : 'Subscribe'),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

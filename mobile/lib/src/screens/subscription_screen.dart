import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/professional.dart';
import '../state/session.dart';
import '../widgets/money_gate.dart';

/// Plan picker + current entitlements — mirrors `web/app/(app)/plans`.
/// Subscribing is gated by the 402 `upgrade_required` shape even here
/// (paradoxically: buying a *higher* plan can itself be blocked, e.g. by
/// `device_cooloff` on the payment method), so it still routes through
/// [MoneyGateBanner].
class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({super.key, required this.session});
  final Session session;

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> {
  List<SubscriptionPlan>? _plans;
  Entitlements? _entitlements;
  String? _busyTier;
  ApiError? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final plans = await widget.session.api.plans();
    final entitlements = await widget.session.api.entitlements();
    if (mounted) {
      setState(() {
        _plans = plans;
        _entitlements = entitlements;
      });
    }
  }

  Future<void> _subscribe(String tier) async {
    setState(() {
      _busyTier = tier;
      _error = null;
    });
    try {
      await widget.session.api.subscribe(tier, 'monthly');
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Plan updated.')));
      }
    } on ApiError catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busyTier = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final plans = _plans;
    final entitlements = _entitlements;
    return Scaffold(
      appBar: AppBar(title: const Text('Plans')),
      body: plans == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (entitlements != null)
                  Card(
                    color: Theme.of(context).colorScheme.surfaceContainerHighest,
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Current plan: ${entitlements.planName}',
                              style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 4),
                          Text(
                            entitlements.proposalQuota == Entitlements.unlimited
                                ? 'Unlimited proposals'
                                : '${entitlements.proposalQuota} proposals / month',
                          ),
                          Text(
                            entitlements.crmContactLimit == Entitlements.unlimited
                                ? 'Unlimited CRM contacts'
                                : '${entitlements.crmContactLimit} CRM contacts',
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                if (_error != null) ...[
                  MoneyGateBanner(error: _error!),
                  const SizedBox(height: 12),
                ],
                for (final plan in plans)
                  Card(
                    margin: const EdgeInsets.only(bottom: 10),
                    child: ListTile(
                      title: Text(plan.name),
                      subtitle: Text('Rs ${plan.monthlyPrice} / month\n${plan.features.join(', ')}'),
                      isThreeLine: true,
                      trailing: entitlements?.tier == plan.tier
                          ? const Chip(label: Text('Current'))
                          : FilledButton(
                              onPressed:
                                  _busyTier != null ? null : () => _subscribe(plan.tier),
                              child: Text(_busyTier == plan.tier ? 'Working…' : 'Choose'),
                            ),
                    ),
                  ),
              ],
            ),
    );
  }
}

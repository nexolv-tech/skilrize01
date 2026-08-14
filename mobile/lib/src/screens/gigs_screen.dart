import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/gigs.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';
import '../widgets/money_gate.dart';

class GigsScreen extends StatelessWidget {
  const GigsScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Services')),
      body: AsyncList<GigSummary>(
        loader: () async => (await session.api.gigs()).results,
        emptyIcon: Icons.storefront_outlined,
        emptyText: 'No gigs published yet.',
        itemBuilder: (context, gig) => Card(
          margin: const EdgeInsets.only(bottom: 10),
          child: ListTile(
            title: Text(gig.title),
            subtitle: Text('${gig.sellerName} · from Rs ${gig.startingPrice}'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => GigDetailScreen(session: session, gigId: gig.id)),
            ),
          ),
        ),
      ),
    );
  }
}

class GigDetailScreen extends StatefulWidget {
  const GigDetailScreen({super.key, required this.session, required this.gigId});
  final Session session;
  final int gigId;

  @override
  State<GigDetailScreen> createState() => _GigDetailScreenState();
}

class _GigDetailScreenState extends State<GigDetailScreen> {
  GigDetail? _gig;
  String? _error;
  GigPackage? _selected;
  bool _ordering = false;
  ApiError? _orderError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final gig = await widget.session.api.gig(widget.gigId);
      if (!mounted) return;
      setState(() {
        _gig = gig;
        _selected = gig.packages.where((p) => p.isActive).firstOrNull;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  /// **Money-moving.** `orderGig` is gated `CanMoveMoney` and captures funds
  /// immediately — a real order, not a cart.
  Future<void> _order() async {
    if (_selected == null) return;
    setState(() {
      _ordering = true;
      _orderError = null;
    });
    try {
      await widget.session.api.orderGig(widget.gigId, package: _selected!.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Order placed. See it under Orders.')),
        );
        Navigator.of(context).pop();
      }
    } on ApiError catch (e) {
      setState(() => _orderError = e);
    } finally {
      if (mounted) setState(() => _ordering = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final gig = _gig;
    return Scaffold(
      appBar: AppBar(title: Text(gig?.title ?? 'Gig')),
      body: _error != null
          ? Center(child: Text(_error!))
          : gig == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(gig.title, style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 4),
                    Text(gig.sellerName, style: Theme.of(context).textTheme.bodyMedium),
                    const SizedBox(height: 16),
                    Text(gig.description),
                    const SizedBox(height: 20),
                    Text('Packages', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    RadioGroup<int>(
                      groupValue: _selected?.id,
                      onChanged: (id) => setState(
                        () => _selected = gig.packages.firstWhere((p) => p.id == id),
                      ),
                      child: Column(
                        children: [
                          for (final package in gig.packages.where((p) => p.isActive))
                            RadioListTile<int>(
                              value: package.id,
                              title: Text('${package.name} — Rs ${package.price}'),
                              subtitle: Text('${package.deliveryDays} day delivery'),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (_orderError != null) ...[
                      MoneyGateBanner(error: _orderError!),
                      const SizedBox(height: 12),
                    ],
                    if (gig.isOwner)
                      const _Note('This is your own gig.')
                    else if (!gig.canOrder)
                      _Note(gig.orderBlockedReason ?? 'This gig cannot be ordered right now.')
                    else
                      FilledButton(
                        onPressed: _selected == null || _ordering ? null : _order,
                        child: Text(_ordering ? 'Placing order…' : 'Order this gig'),
                      ),
                  ],
                ),
    );
  }
}

class _Note extends StatelessWidget {
  const _Note(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(text),
      );
}

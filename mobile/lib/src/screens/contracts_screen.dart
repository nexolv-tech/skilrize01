import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/models.dart';
import '../state/session.dart';
import '../theme.dart';

/// Contracts the signed-in user is a party to, and their milestones.
///
/// Read-only, deliberately. Funding and releasing money are gated behind
/// `CanMoveMoney` — a confirmed second factor plus a cleared device
/// cool-off — and a half-built money action on a phone is worse than none.
/// The states are shown honestly; acting on them stays on the web client
/// until the mobile money flow is designed properly.
class ContractsScreen extends StatefulWidget {
  const ContractsScreen({super.key, required this.session});

  final Session session;

  @override
  State<ContractsScreen> createState() => _ContractsScreenState();
}

class _ContractsScreenState extends State<ContractsScreen> {
  List<ContractSummary>? _contracts;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await widget.session.api.contracts();
      if (!mounted) return;
      setState(() {
        _contracts = page.results;
        _loading = false;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Contracts')),
      body: _body(context),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!),
            TextButton(onPressed: _load, child: const Text('Try again')),
          ],
        ),
      );
    }

    final contracts = _contracts ?? const [];
    if (contracts.isEmpty) {
      return const Center(child: Text('No contracts yet.'));
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: contracts.length,
        itemBuilder: (context, i) {
          final contract = contracts[i];
          final scheme = Theme.of(context).colorScheme;
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              title: Text(contract.title),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  '${contract.myRole == 'client' ? contract.freelancerName : contract.clientName}'
                  ' · Rs ${contract.headlineAmount}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              trailing: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor(scheme, contract.status).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  contract.status,
                  style: TextStyle(fontSize: 12, color: statusColor(scheme, contract.status)),
                ),
              ),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => ContractDetailScreen(
                    session: widget.session,
                    contractId: contract.id,
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class ContractDetailScreen extends StatefulWidget {
  const ContractDetailScreen({super.key, required this.session, required this.contractId});

  final Session session;
  final int contractId;

  @override
  State<ContractDetailScreen> createState() => _ContractDetailScreenState();
}

class _ContractDetailScreenState extends State<ContractDetailScreen> {
  ContractDetail? _contract;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final contract = await widget.session.api.contract(widget.contractId);
      if (!mounted) return;
      setState(() => _contract = contract);
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final contract = _contract;
    return Scaffold(
      appBar: AppBar(title: Text(contract?.title ?? 'Contract')),
      body: _error != null
          ? Center(child: Text(_error!))
          : contract == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _row(context, 'Status', contract.status),
                            _row(context, 'Type', contract.contractType),
                            _row(context, 'Value', 'Rs ${contract.headlineAmount}'),
                            _row(context, 'Held in escrow', 'Rs ${contract.fundedAmount}'),
                            _row(context, 'Released', 'Rs ${contract.releasedAmount}'),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text('Milestones', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    if (contract.milestones.isEmpty)
                      const Text('No milestones on this contract.')
                    else
                      for (final milestone in contract.milestones)
                        Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            title: Text(milestone.title),
                            subtitle: Text('Rs ${milestone.amount}'),
                            trailing: Text(
                              milestone.status,
                              style: TextStyle(
                                color: statusColor(
                                    Theme.of(context).colorScheme, milestone.status),
                              ),
                            ),
                          ),
                        ),
                  ],
                ),
    );
  }

  Widget _row(BuildContext context, String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            Text(value, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      );
}

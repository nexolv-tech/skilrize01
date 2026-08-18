import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/payments.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';
import '../widgets/money_gate.dart';

/// Where a freelancer's released milestones actually get paid — typed in
/// once, then read by whoever on the platform side sends the manual bank
/// transfer on release. Nothing here verifies the account; there is no
/// gateway to ask (Phase 3, D42).
class PayoutsScreen extends StatefulWidget {
  const PayoutsScreen({super.key, required this.session});
  final Session session;

  @override
  State<PayoutsScreen> createState() => _PayoutsScreenState();
}

class _PayoutsScreenState extends State<PayoutsScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 2, vsync: this);
  PayoutProfile? _profile;
  bool _loadingProfile = true;

  final _bankName = TextEditingController();
  final _accountTitle = TextEditingController();
  final _accountNumber = TextEditingController();
  final _cnic = TextEditingController();
  final _msisdn = TextEditingController();

  bool _busy = false;
  bool _saved = false;
  ApiError? _error;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _bankName.dispose();
    _accountTitle.dispose();
    _accountNumber.dispose();
    _cnic.dispose();
    _msisdn.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    try {
      final profile = await widget.session.api.payoutProfile();
      if (mounted) setState(() => _profile = profile);
    } on ApiError catch (_) {
      // A fresh account has no profile yet — the form below handles that.
    } finally {
      if (mounted) setState(() => _loadingProfile = false);
    }
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.session.api.savePayoutProfile(
        bankName: _bankName.text.trim(),
        accountTitle: _accountTitle.text.trim(),
        accountNumber: _accountNumber.text.trim(),
        cnic: _cnic.text.trim(),
        msisdn: _msisdn.text.trim(),
      );
      _bankName.clear();
      _accountTitle.clear();
      _accountNumber.clear();
      _cnic.clear();
      _msisdn.clear();
      setState(() => _saved = true);
      Future.delayed(const Duration(seconds: 3), () {
        if (mounted) setState(() => _saved = false);
      });
      await _loadProfile();
    } on ApiError catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Payouts'),
        bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Account'), Tab(text: 'History')]),
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          _loadingProfile
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_profile?.isComplete ?? false)
                      Container(
                        padding: const EdgeInsets.all(12),
                        margin: const EdgeInsets.only(bottom: 16),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          'Currently paying out to ${_profile!.accountTitle} at '
                          '${_profile!.bankName}. Saving a new account below replaces this one.',
                        ),
                      ),
                    if (_error != null) ...[
                      MoneyGateBanner(error: _error!),
                      const SizedBox(height: 12),
                    ],
                    TextField(
                      controller: _bankName,
                      decoration: const InputDecoration(labelText: 'Bank name', hintText: 'Habib Bank'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _accountTitle,
                      decoration: const InputDecoration(
                        labelText: 'Account title',
                        hintText: 'Ahmed Raza',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _accountNumber,
                      decoration: const InputDecoration(
                        labelText: 'Account / IBAN number',
                        hintText: 'PK00HABB0000001234567',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _cnic,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'CNIC', hintText: '4210112345671'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _msisdn,
                      keyboardType: TextInputType.phone,
                      decoration:
                          const InputDecoration(labelText: 'Mobile number', hintText: '03001234567'),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        FilledButton(
                          onPressed: _busy ? null : _save,
                          child: Text(_busy ? 'Saving…' : 'Save payout account'),
                        ),
                        if (_saved) ...[
                          const SizedBox(width: 10),
                          const Icon(Icons.check_circle, color: Colors.green, size: 20),
                        ],
                      ],
                    ),
                  ],
                ),
          AsyncList<Payout>(
            loader: () async => (await widget.session.api.myPayouts()).results,
            emptyIcon: Icons.account_balance_wallet_outlined,
            emptyText: "No payouts yet — they'll show up here once a client releases a milestone.",
            itemBuilder: (context, payout) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(payout.milestoneTitle),
                subtitle: Text(
                  'Rs ${payout.grossAmount} minus ${payout.commissionPercent}% fee',
                ),
                trailing: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text('Rs ${payout.netAmount}'),
                    StatusPill(payout.status),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

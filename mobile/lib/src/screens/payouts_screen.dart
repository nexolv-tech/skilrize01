import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/payments.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';
import '../widgets/money_gate.dart';

/// Where a freelancer's released milestones actually get paid — set up
/// once, verified once (the bank tells us whose name is on the account
/// before it's saved, not the other way round), then it just sits behind
/// every future release. Phase 3, D41.
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

  final _bankCode = TextEditingController();
  final _bankName = TextEditingController();
  final _accountNumber = TextEditingController();
  final _cnic = TextEditingController();
  final _msisdn = TextEditingController();

  String? _verifiedTitle;
  bool _busy = false;
  ApiError? _error;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _bankCode.dispose();
    _bankName.dispose();
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

  void _resetTitleOnEdit() {
    if (_verifiedTitle != null) setState(() => _verifiedTitle = null);
  }

  Future<void> _verifyOrSave() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_verifiedTitle == null) {
        final title = await widget.session.api.verifyPayoutTitle(
          bankCode: _bankCode.text.trim(),
          bankName: _bankName.text.trim(),
          accountNumber: _accountNumber.text.trim(),
          msisdn: _msisdn.text.trim(),
        );
        setState(() => _verifiedTitle = title);
      } else {
        await widget.session.api.savePayoutProfile(
          bankCode: _bankCode.text.trim(),
          bankName: _bankName.text.trim(),
          accountNumber: _accountNumber.text.trim(),
          cnic: _cnic.text.trim(),
          msisdn: _msisdn.text.trim(),
        );
        _bankCode.clear();
        _bankName.clear();
        _accountNumber.clear();
        _cnic.clear();
        _msisdn.clear();
        setState(() => _verifiedTitle = null);
        await _loadProfile();
      }
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
                          'Currently paying out to ${_profile!.verifiedAccountTitle} at '
                          '${_profile!.bankName}. Saving a new account below replaces this one.',
                        ),
                      ),
                    if (_error != null) ...[
                      MoneyGateBanner(error: _error!),
                      const SizedBox(height: 12),
                    ],
                    TextField(
                      controller: _bankCode,
                      onChanged: (_) => _resetTitleOnEdit(),
                      textCapitalization: TextCapitalization.characters,
                      decoration: const InputDecoration(
                        labelText: 'Bank code',
                        hintText: 'HABB',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _bankName,
                      onChanged: (_) => _resetTitleOnEdit(),
                      decoration: const InputDecoration(labelText: 'Bank name', hintText: 'Habib Bank'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _accountNumber,
                      onChanged: (_) => _resetTitleOnEdit(),
                      decoration: const InputDecoration(
                        labelText: 'Account / IBAN number',
                        hintText: 'PK00HABB0000001234567',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _cnic,
                      keyboardType: TextInputType.number,
                      onChanged: (_) => _resetTitleOnEdit(),
                      decoration: const InputDecoration(labelText: 'CNIC', hintText: '4210112345671'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _msisdn,
                      keyboardType: TextInputType.phone,
                      onChanged: (_) => _resetTitleOnEdit(),
                      decoration:
                          const InputDecoration(labelText: 'Mobile number', hintText: '03001234567'),
                    ),
                    const SizedBox(height: 16),
                    if (_verifiedTitle != null) ...[
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.green.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          'This account belongs to $_verifiedTitle. Save it if that\'s you.',
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],
                    FilledButton(
                      onPressed: _busy ? null : _verifyOrSave,
                      child: Text(
                        _busy
                            ? 'Working…'
                            : (_verifiedTitle == null ? 'Verify account' : 'Save payout account'),
                      ),
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
                subtitle: payout.status == 'failed' && payout.failureReason.isNotEmpty
                    ? Text(payout.failureReason)
                    : null,
                trailing: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text('Rs ${payout.amount}'),
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

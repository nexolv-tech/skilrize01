import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/misc.dart';
import '../state/session.dart';

/// Settings home: profile fields, and links into security and notification
/// preferences (each large enough to earn its own screen).
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.session});

  final Session session;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final _fullName = TextEditingController(text: widget.session.user?.displayName);
  late final _headline = TextEditingController(text: widget.session.user?.headline);
  bool _saving = false;
  String? _error;
  bool _saved = false;

  @override
  void dispose() {
    _fullName.dispose();
    _headline.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.session.api
          .updateMe({'full_name': _fullName.text.trim(), 'headline': _headline.text.trim()});
      await widget.session.refreshUser();
      if (mounted) setState(() => _saved = true);
    } on ApiError catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Profile', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          if (_error != null) ...[
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            const SizedBox(height: 8),
          ],
          TextField(
            controller: _fullName,
            decoration: const InputDecoration(labelText: 'Full name'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _headline,
            decoration: const InputDecoration(labelText: 'Headline'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              FilledButton(
                onPressed: _saving ? null : _save,
                child: Text(_saving ? 'Saving…' : 'Save'),
              ),
              if (_saved) ...[
                const SizedBox(width: 10),
                const Icon(Icons.check, color: Colors.green),
              ],
            ],
          ),
          const Divider(height: 40),
          ListTile(
            leading: const Icon(Icons.shield_outlined),
            title: const Text('Security'),
            subtitle: const Text('Two-factor authentication, sessions, password'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => SecuritySettingsScreen(session: widget.session)),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.notifications_outlined),
            title: const Text('Notifications'),
            subtitle: const Text('What you hear about, and how'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                  builder: (_) => NotificationSettingsScreen(session: widget.session)),
            ),
          ),
        ],
      ),
    );
  }
}

/// 2FA enrolment, sessions, and password change.
class SecuritySettingsScreen extends StatefulWidget {
  const SecuritySettingsScreen({super.key, required this.session});
  final Session session;

  @override
  State<SecuritySettingsScreen> createState() => _SecuritySettingsScreenState();
}

class _SecuritySettingsScreenState extends State<SecuritySettingsScreen> {
  List<AuthSession>? _sessions;
  String? _error;
  Map<String, dynamic>? _enrolment;
  final _code = TextEditingController();
  bool _busy = false;
  List<String>? _recoveryCodes;

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _loadSessions() async {
    try {
      final sessions = await widget.session.api.sessions();
      if (!mounted) return;
      setState(() => _sessions = sessions);
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _beginEnrolment() async {
    setState(() => _busy = true);
    try {
      final result = await widget.session.api.twoFactorSetup();
      if (mounted) setState(() => _enrolment = result);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirmEnrolment() async {
    setState(() => _busy = true);
    try {
      final codes = await widget.session.api.twoFactorConfirm(_code.text.trim());
      await widget.session.refreshUser();
      if (mounted) {
        setState(() {
          _recoveryCodes = codes;
          _enrolment = null;
        });
      }
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _revoke(String family) async {
    await widget.session.api.revokeSession(family);
    _loadSessions();
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.session.user;
    return Scaffold(
      appBar: AppBar(title: const Text('Security')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Two-factor authentication', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_recoveryCodes != null) ...[
            const Text('Two-factor authentication is on. Save these recovery codes — '
                'each works once, and this is the only time they are shown.'),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final code in _recoveryCodes!)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(code, style: const TextStyle(fontFamily: 'monospace')),
                  ),
              ],
            ),
          ] else if (user?.hasTwoFactor ?? false)
            const Row(children: [Icon(Icons.check_circle, color: Colors.green), SizedBox(width: 8), Text('Enabled')])
          else if (_enrolment != null) ...[
            Text('Scan the QR in an authenticator app, then enter the code:',
                style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 8),
            SelectableText(_enrolment!['secret'] as String? ?? '',
                style: const TextStyle(fontFamily: 'monospace')),
            const SizedBox(height: 10),
            TextField(
              controller: _code,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Code'),
            ),
            const SizedBox(height: 10),
            FilledButton(
              onPressed: _busy ? null : _confirmEnrolment,
              child: Text(_busy ? 'Confirming…' : 'Enable'),
            ),
          ] else
            FilledButton.tonal(
              onPressed: _busy ? null : _beginEnrolment,
              child: const Text('Set up two-factor authentication'),
            ),
          const Divider(height: 40),
          Text('Active sessions', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_error != null) Text(_error!),
          if (_sessions == null)
            const Center(child: CircularProgressIndicator())
          else
            for (final s in _sessions!)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.devices_outlined),
                title: Text(s.deviceLabel.isEmpty ? 'Unknown device' : s.deviceLabel),
                subtitle: Text(s.ipAddress ?? ''),
                trailing: s.isCurrent
                    ? const Chip(label: Text('This device'))
                    : TextButton(
                        onPressed: () => _revoke(s.family),
                        child: const Text('Revoke'),
                      ),
              ),
        ],
      ),
    );
  }
}

/// Per-category, per-channel notification toggles.
class NotificationSettingsScreen extends StatefulWidget {
  const NotificationSettingsScreen({super.key, required this.session});
  final Session session;

  @override
  State<NotificationSettingsScreen> createState() => _NotificationSettingsScreenState();
}

class _NotificationSettingsScreenState extends State<NotificationSettingsScreen> {
  Map<String, dynamic>? _prefs;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final prefs = await widget.session.api.notificationPreferences();
      if (mounted) setState(() => _prefs = prefs);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final prefs = _prefs;
    final categories = (prefs?['categories'] as List?) ?? const [];
    final overrides = Map<String, dynamic>.from(prefs?['overrides'] as Map? ?? {});

    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: _error != null
          ? Center(child: Text(_error!))
          : prefs == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    for (final category in categories)
                      SwitchListTile(
                        title: Text((category as Map)['label'] as String? ?? ''),
                        value: (overrides[category['value']] as Map?)?['email'] != false,
                        onChanged: (value) async {
                          final next = Map<String, dynamic>.from(overrides);
                          next[category['value']] = {'email': value, 'push': value};
                          await widget.session.api
                              .updateNotificationPreferences({'overrides': next});
                          _load();
                        },
                      ),
                  ],
                ),
    );
  }
}

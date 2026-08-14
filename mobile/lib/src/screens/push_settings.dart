import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb, TargetPlatform;
import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../state/session.dart';

/// Registering this device for push, against the Phase 7 backend.
///
/// **Gated on `config.push_enabled`.** The OS grants exactly one chance to
/// ask for notification permission; spending it on a deployment whose FCM
/// credentials are not configured means the user says yes to nothing and
/// cannot be asked again. `/config/` exists to answer that question before
/// the prompt, which is why the card renders as unavailable rather than
/// hopeful when the server says push is off.
///
/// **The FCM token itself is not obtained here.** `firebase_messaging`
/// requires a real Firebase project — `google-services.json` for Android, an
/// APNs key for iOS — and neither exists for this environment. What is real
/// is everything this side of that call: the gate, the registration request,
/// the unregister on sign-out, and the platform tag the server stores. The
/// day a Firebase project exists, the one `TODO` below is a single call, not
/// a redesign.
class PushSettingsCard extends StatefulWidget {
  const PushSettingsCard({super.key, required this.session});

  final Session session;

  @override
  State<PushSettingsCard> createState() => _PushSettingsCardState();
}

class _PushSettingsCardState extends State<PushSettingsCard> {
  bool _busy = false;
  String? _message;

  /// What the server records this installation as. Matches
  /// `PushDevice.Platform` exactly — an unknown value is a 400, not a
  /// silently mislabelled row.
  String get _platform {
    if (kIsWeb) return 'web';
    return switch (defaultTargetPlatform) {
      TargetPlatform.iOS => 'ios',
      TargetPlatform.android => 'android',
      _ => 'web',
    };
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.session.pushEnabled;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(enabled ? Icons.notifications_active_outlined
                             : Icons.notifications_off_outlined),
                const SizedBox(width: 8),
                Text('Push notifications',
                    style: Theme.of(context).textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              enabled
                  ? 'Register this device to receive alerts about contracts, '
                      'messages, and payments.'
                  : 'Not available on this deployment — the server has no push '
                      'provider configured, so this app will not ask for '
                      'notification permission.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (_message != null) ...[
              const SizedBox(height: 10),
              Text(_message!, style: Theme.of(context).textTheme.bodySmall),
            ],
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: (!enabled || _busy) ? null : _register,
              child: Text(_busy ? 'Registering…' : 'Register this device'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _register() async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      // TODO(phase7): replace with FirebaseMessaging.instance.getToken()
      // once a Firebase project exists. Until then there is no real token to
      // send, and inventing one would register a device that can never
      // receive anything.
      const token = null;
      if (token == null) {
        setState(() => _message =
            'No push provider configured, so there is no device token to register.');
        return;
      }
      await widget.session.api.registerPushDevice(token: token, platform: _platform);
      setState(() => _message = 'This device is registered.');
    } on ApiError catch (e) {
      setState(() => _message = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

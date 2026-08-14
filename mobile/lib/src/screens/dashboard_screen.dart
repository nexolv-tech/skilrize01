import 'package:flutter/material.dart';

import '../state/session.dart';
import 'push_settings.dart';

/// Account state: what's verified, what isn't, and what that unlocks.
///
/// The verification gate is the first thing a new account hits on any
/// client, so it is the first thing here — showing a marketplace they cannot
/// yet transact in, without saying why, is how the web app's dashboard used
/// to read before it led with this.
class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key, required this.session});

  final Session session;

  static const _labels = {
    'email': 'Confirm your email',
    'phone': 'Verify your phone',
    'identity': 'Verify your identity',
  };

  @override
  Widget build(BuildContext context) {
    final user = session.user!;
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Overview'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: session.signOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            user.displayName.isEmpty ? user.email : user.displayName,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          if (user.headline.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(user.headline, style: Theme.of(context).textTheme.bodyMedium),
          ],
          const SizedBox(height: 20),

          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        user.canTransact ? Icons.verified_outlined : Icons.pending_outlined,
                        color: user.canTransact ? Colors.green.shade600 : scheme.outline,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        user.canTransact ? 'Ready to transact' : 'Restricted',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  LinearProgressIndicator(value: user.profileStrength / 100),
                  const SizedBox(height: 6),
                  Text('Profile strength ${user.profileStrength}%',
                      style: Theme.of(context).textTheme.bodySmall),
                  if (user.missingRequirements.isNotEmpty) ...[
                    const SizedBox(height: 14),
                    Text(
                      '${user.missingRequirements.length} check'
                      '${user.missingRequirements.length == 1 ? '' : 's'} left before you can '
                      'post, sell, or buy. You can browse freely in the meantime.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 10),
                    for (final requirement in user.missingRequirements)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        child: Row(
                          children: [
                            Icon(Icons.circle_outlined, size: 16, color: scheme.outline),
                            const SizedBox(width: 8),
                            Text(_labels[requirement] ?? requirement),
                          ],
                        ),
                      ),
                  ],
                ],
              ),
            ),
          ),

          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: Icon(
                user.hasTwoFactor ? Icons.lock_outline : Icons.lock_open_outlined,
                color: user.hasTwoFactor ? Colors.green.shade600 : scheme.outline,
              ),
              title: const Text('Two-factor authentication'),
              subtitle: Text(user.hasTwoFactor ? 'Enabled' : 'Not set up'),
            ),
          ),

          const SizedBox(height: 12),
          PushSettingsCard(session: session),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../state/session.dart';
import 'admin_screen.dart';
import 'agency_screen.dart';
import 'crm_screen.dart';
import 'feed_screen.dart';
import 'integrations_screen.dart';
import 'notifications_screen.dart';
import 'retainers_screen.dart';
import 'settings_screen.dart';
import 'student_screen.dart';
import 'subscription_screen.dart';

/// Everything that doesn't fit the four main tabs — the professional layer,
/// account settings, and anything role-gated. Mirrors how the web app's
/// header/sidebar groups "account and business" links away from the core
/// work loop; here that grouping becomes a single screen instead of a menu.
class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    final isAdmin = session.user?.adminRole.isNotEmpty ?? false;

    final entries = <(IconData, String, WidgetBuilder)>[
      (Icons.notifications_outlined, 'Notifications', (_) => NotificationsScreen(session: session)),
      (Icons.dynamic_feed_outlined, 'Feed & showcase', (_) => FeedScreen(session: session)),
      (Icons.school_outlined, 'Student verification', (_) => StudentScreen(session: session)),
      (Icons.workspace_premium_outlined, 'Plans & subscription', (_) => SubscriptionScreen(session: session)),
      (Icons.contacts_outlined, 'CRM', (_) => CrmScreen(session: session)),
      (Icons.repeat_outlined, 'Retainers', (_) => RetainersScreen(session: session)),
      (Icons.groups_2_outlined, 'Agency & workspaces', (_) => AgencyScreen(session: session)),
      (Icons.link_outlined, 'Integrations', (_) => IntegrationsScreen(session: session)),
      if (isAdmin) (Icons.admin_panel_settings_outlined, 'Admin console', (_) => AdminScreen(session: session)),
      (Icons.settings_outlined, 'Settings', (_) => SettingsScreen(session: session)),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('More')),
      body: ListView.separated(
        itemCount: entries.length,
        separatorBuilder: (_, __) => const Divider(height: 1),
        itemBuilder: (context, i) {
          final (icon, title, builder) = entries[i];
          return ListTile(
            leading: Icon(icon),
            title: Text(title),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: builder)),
          );
        },
      ),
    );
  }
}

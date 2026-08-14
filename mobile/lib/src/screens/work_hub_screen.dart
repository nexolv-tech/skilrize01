import 'package:flutter/material.dart';

import '../state/session.dart';
import 'challenges_screen.dart';
import 'communities_screen.dart';
import 'gigs_screen.dart';
import 'orders_screen.dart';
import 'projects_screen.dart';
import 'proposals_screen.dart';
import 'search_screen.dart';

/// Everything about finding and doing work, one tap away from the bottom
/// nav's "Work" tab. The web app spreads these across separate top-level
/// routes because a desktop nav has the room; on a phone they group under
/// one hub instead of eating five more bottom-nav slots.
class WorkHubScreen extends StatelessWidget {
  const WorkHubScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    final entries = <(IconData, String, String, WidgetBuilder)>[
      (Icons.search, 'Search', 'Find gigs and projects', (_) => SearchScreen(session: session)),
      (Icons.work_outline, 'Projects', 'Browse open projects', (_) => ProjectsScreen(session: session)),
      (Icons.send_outlined, 'My proposals', 'Track what you have pitched', (_) => ProposalsScreen(session: session)),
      (Icons.storefront_outlined, 'Gigs', 'Browse services for sale', (_) => GigsScreen(session: session)),
      (Icons.receipt_long_outlined, 'Orders', 'Gigs you bought or sold', (_) => OrdersScreen(session: session)),
      (Icons.groups_outlined, 'Communities', 'Threads, events, resources', (_) => CommunitiesScreen(session: session)),
      (Icons.emoji_events_outlined, 'Challenges', 'Proof-of-work challenges', (_) => ChallengesScreen(session: session)),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Work')),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: entries.length,
        itemBuilder: (context, i) {
          final (icon, title, subtitle, builder) = entries[i];
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: ListTile(
              leading: Icon(icon),
              title: Text(title),
              subtitle: Text(subtitle),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: builder)),
            ),
          );
        },
      ),
    );
  }
}

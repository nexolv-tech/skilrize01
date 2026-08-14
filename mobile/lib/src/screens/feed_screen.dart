import 'package:flutter/material.dart';

import '../models/communities.dart';
import '../models/misc.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

/// Activity feed + portfolio showcase — mirrors `web/app/(app)/feed` and
/// `.../showcase`. Two tabs rather than two destinations, since neither is
/// dense enough on its own to earn a bottom-nav slot.
class FeedScreen extends StatefulWidget {
  const FeedScreen({super.key, required this.session});
  final Session session;

  @override
  State<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends State<FeedScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 2, vsync: this);

  static const _verbIcons = {
    'proposal_accepted': Icons.handshake_outlined,
    'contract_completed': Icons.task_alt,
    'review_posted': Icons.star_outline,
    'gig_published': Icons.storefront_outlined,
    'challenge_won': Icons.emoji_events_outlined,
  };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Feed'),
        bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Activity'), Tab(text: 'Showcase')]),
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          AsyncList<FeedEntry>(
            loader: () async => (await widget.session.api.feed()).results,
            emptyIcon: Icons.dynamic_feed_outlined,
            emptyText: 'Nothing in your feed yet.',
            itemBuilder: (context, entry) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: Icon(_verbIcons[entry.verb] ?? Icons.circle_notifications_outlined),
                title: Text(entry.summary),
                subtitle: Text(_relative(entry.createdAt)),
              ),
            ),
          ),
          AsyncList<ShowcasePiece>(
            loader: () async => (await widget.session.api.showcase()).results,
            emptyIcon: Icons.auto_awesome_outlined,
            emptyText: 'No showcase pieces yet.',
            itemBuilder: (context, piece) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(piece.title),
                subtitle: piece.summary.isEmpty ? null : Text(piece.summary),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _relative(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

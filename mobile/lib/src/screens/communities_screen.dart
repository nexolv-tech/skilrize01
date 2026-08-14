import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/communities.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

class CommunitiesScreen extends StatelessWidget {
  const CommunitiesScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Communities')),
      body: AsyncList<Community>(
        loader: () async => (await session.api.communities()).results,
        emptyIcon: Icons.groups_outlined,
        emptyText: 'No communities yet.',
        itemBuilder: (context, community) => Card(
          margin: const EdgeInsets.only(bottom: 10),
          child: ListTile(
            title: Text(community.name),
            subtitle: Text('${community.memberCount} members · ${community.kind}'),
            trailing: community.isMember ? const Icon(Icons.check_circle, color: Colors.green) : null,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => CommunityDetailScreen(session: session, communityId: community.id),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class CommunityDetailScreen extends StatefulWidget {
  const CommunityDetailScreen({super.key, required this.session, required this.communityId});
  final Session session;
  final int communityId;

  @override
  State<CommunityDetailScreen> createState() => _CommunityDetailScreenState();
}

class _CommunityDetailScreenState extends State<CommunityDetailScreen>
    with SingleTickerProviderStateMixin {
  Community? _community;
  late final TabController _tabs = TabController(length: 3, vsync: this);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final community = await widget.session.api.community(widget.communityId);
      if (mounted) setState(() => _community = community);
    } on ApiError {
      // Header just won't render; the tabs below still work independently.
    }
  }

  Future<void> _toggleMembership() async {
    final community = _community;
    if (community == null) return;
    if (community.isMember) {
      await widget.session.api.leaveCommunity(community.id);
    } else {
      await widget.session.api.joinCommunity(community.id);
    }
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_community?.name ?? 'Community'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [Tab(text: 'Threads'), Tab(text: 'Events'), Tab(text: 'Resources')],
        ),
        actions: [
          if (_community != null)
            TextButton(
              onPressed: _toggleMembership,
              child: Text(_community!.isMember ? 'Leave' : 'Join',
                  style: const TextStyle(color: Colors.white)),
            ),
        ],
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          AsyncList<CommunityThread>(
            loader: () async => (await widget.session.api.threads(widget.communityId)).results,
            emptyIcon: Icons.forum_outlined,
            emptyText: 'No threads yet.',
            itemBuilder: (context, thread) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(thread.title),
                subtitle: Text('${thread.replyCount} replies · ${thread.authorName}'),
                leading: thread.isPinned ? const Icon(Icons.push_pin_outlined) : null,
              ),
            ),
          ),
          AsyncList<CommunityEvent>(
            loader: () async =>
                (await widget.session.api.communityEvents(communityId: widget.communityId)).results,
            emptyIcon: Icons.event_outlined,
            emptyText: 'No events scheduled.',
            itemBuilder: (context, event) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(event.title),
                subtitle: Text(event.startsAt.toString()),
                trailing: PopupMenuButton<String>(
                  onSelected: (response) async {
                    await widget.session.api.rsvp(event.id, response);
                  },
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: 'going', child: Text('Going')),
                    PopupMenuItem(value: 'interested', child: Text('Interested')),
                    PopupMenuItem(value: 'declined', child: Text("Can't go")),
                  ],
                  child: Text(event.myRsvp ?? 'RSVP'),
                ),
              ),
            ),
          ),
          AsyncList<CommunityResource>(
            loader: () async =>
                (await widget.session.api.resources(communityId: widget.communityId)).results,
            emptyIcon: Icons.link_outlined,
            emptyText: 'No resources shared yet.',
            itemBuilder: (context, resource) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: const Icon(Icons.link),
                title: Text(resource.title),
                subtitle: Text(resource.url, maxLines: 1, overflow: TextOverflow.ellipsis),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

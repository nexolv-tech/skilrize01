import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/professional.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';
import '../widgets/money_gate.dart';

/// Agencies (teams) + shared workspaces — mirrors `web/app/(app)/agency`.
/// Both lists are read/create only here; member invites and workspace
/// document management stay web-only for this pass, same as the web app's
/// own admin-heavy surfaces the mobile client doesn't attempt to replicate.
class AgencyScreen extends StatefulWidget {
  const AgencyScreen({super.key, required this.session});
  final Session session;

  @override
  State<AgencyScreen> createState() => _AgencyScreenState();
}

class _AgencyScreenState extends State<AgencyScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 2, vsync: this);
  final _teamsKey = GlobalKey<AsyncListState<AgencyTeam>>();
  ApiError? _error;
  bool _creating = false;

  Future<void> _createAgency() async {
    final controller = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('New agency'),
        content: TextField(controller: controller, decoration: const InputDecoration(labelText: 'Name')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    setState(() {
      _creating = true;
      _error = null;
    });
    try {
      await widget.session.api.createAgency(name);
      _teamsKey.currentState?.reload();
    } on ApiError catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Agency'),
        bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Teams'), Tab(text: 'Workspaces')]),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: _creating ? null : _createAgency,
          ),
        ],
      ),
      body: Column(
        children: [
          if (_error != null)
            Padding(padding: const EdgeInsets.all(12), child: MoneyGateBanner(error: _error!)),
          Expanded(
            child: TabBarView(
              controller: _tabs,
              children: [
                AsyncList<AgencyTeam>(
                  key: _teamsKey,
                  loader: () async => (await widget.session.api.agencies()).results,
                  emptyIcon: Icons.groups_2_outlined,
                  emptyText: 'No agency yet.',
                  itemBuilder: (context, team) => Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      title: Text(team.name),
                      subtitle: Text('${team.memberCount} members'),
                    ),
                  ),
                ),
                AsyncList<SharedWorkspace>(
                  loader: () async => (await widget.session.api.workspaces()).results,
                  emptyIcon: Icons.folder_shared_outlined,
                  emptyText: 'No shared workspaces yet.',
                  itemBuilder: (context, workspace) => Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(title: Text(workspace.name)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

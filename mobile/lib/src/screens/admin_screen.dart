import 'package:flutter/material.dart';

import '../models/misc.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

/// Role-gated admin console — verifications, users, audit log. Visibility is
/// decided by [Session.user]'s `adminRole` (empty string = not an admin);
/// the server enforces the real gate on every one of these endpoints
/// regardless, so a client bypass here would just get 403s, not access.
class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key, required this.session});
  final Session session;

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 3, vsync: this);
  final _verificationsKey = GlobalKey<AsyncListState<AdminVerification>>();
  final _usersKey = GlobalKey<AsyncListState<AdminUserRow>>();

  Future<void> _reject(int id) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject verification'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Reason'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    if (reason == null || reason.isEmpty) return;
    await widget.session.api.rejectVerification(id, reason);
    _verificationsKey.currentState?.reload();
  }

  Future<void> _suspend(int id) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Suspend user'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Reason'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Suspend'),
          ),
        ],
      ),
    );
    if (reason == null || reason.isEmpty) return;
    await widget.session.api.suspendUser(id, reason);
    _usersKey.currentState?.reload();
  }

  @override
  Widget build(BuildContext context) {
    final isAdmin = widget.session.user?.adminRole.isNotEmpty ?? false;
    if (!isAdmin) {
      return Scaffold(
        appBar: AppBar(title: const Text('Admin')),
        body: const Center(child: Text('Admin access required.')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [Tab(text: 'Verifications'), Tab(text: 'Users'), Tab(text: 'Audit log')],
        ),
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          AsyncList<AdminVerification>(
            key: _verificationsKey,
            loader: () async => (await widget.session.api.adminVerifications(status: 'pending')).results,
            emptyIcon: Icons.verified_outlined,
            emptyText: 'No pending verifications.',
            itemBuilder: (context, v) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(v.applicantName),
                subtitle: Text(v.universityName),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.check, color: Colors.green),
                      onPressed: () async {
                        await widget.session.api.approveVerification(v.id);
                        _verificationsKey.currentState?.reload();
                      },
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.red),
                      onPressed: () => _reject(v.id),
                    ),
                  ],
                ),
              ),
            ),
          ),
          AsyncList<AdminUserRow>(
            key: _usersKey,
            loader: () async => (await widget.session.api.adminUsers()).results,
            emptyIcon: Icons.people_outline,
            emptyText: 'No users found.',
            itemBuilder: (context, user) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(user.displayName.isEmpty ? user.email : user.displayName),
                subtitle: Text(user.email),
                trailing: user.isActive
                    ? TextButton(onPressed: () => _suspend(user.id), child: const Text('Suspend'))
                    : TextButton(
                        onPressed: () async {
                          await widget.session.api.reactivateUser(user.id);
                          _usersKey.currentState?.reload();
                        },
                        child: const Text('Reactivate'),
                      ),
              ),
            ),
          ),
          AsyncList<AuditLogEntry>(
            loader: () async => (await widget.session.api.auditLog()).results,
            emptyIcon: Icons.history,
            emptyText: 'No audit log entries.',
            itemBuilder: (context, entry) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(entry.action),
                subtitle: Text('${entry.actorName ?? 'System'} · ${entry.createdAt}'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

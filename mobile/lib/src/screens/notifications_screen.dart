import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/models.dart';
import '../state/session.dart';

/// The in-app notification centre.
///
/// The same rows push delivery fans out from (`core/notify.py` writes every
/// notification here first, then queues the channels) — so this list is
/// correct whether or not FCM is configured, which is exactly why it is the
/// notification surface the app can rely on today.
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key, required this.session});

  final Session session;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<AppNotification>? _items;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await widget.session.api.notifications();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _markAllRead() async {
    await widget.session.api.markNotificationsRead();
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final unread = (_items ?? const []).where((n) => !n.isRead).length;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          if (unread > 0)
            TextButton(onPressed: _markAllRead, child: const Text('Mark all read')),
        ],
      ),
      body: _body(context),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!),
            TextButton(onPressed: _load, child: const Text('Try again')),
          ],
        ),
      );
    }

    final items = _items ?? const [];
    if (items.isEmpty) return const Center(child: Text('Nothing yet.'));

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        itemCount: items.length,
        separatorBuilder: (_, __) => const Divider(height: 1),
        itemBuilder: (context, i) {
          final item = items[i];
          return ListTile(
            leading: Icon(
              item.isRead ? Icons.circle_outlined : Icons.circle,
              size: 12,
              color: item.isRead
                  ? Theme.of(context).colorScheme.outline
                  : Theme.of(context).colorScheme.primary,
            ),
            title: Text(item.title),
            subtitle: item.body.isEmpty ? null : Text(item.body),
            trailing: Text(
              item.category,
              style: Theme.of(context).textTheme.labelSmall,
            ),
          );
        },
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../api/api_error.dart';

/// The loading/error/empty/data states every list screen in this app needs,
/// written once. Fifteen-plus screens each independently reimplementing
/// "show a spinner, then a retry button, then a real list" is how a small
/// inconsistency (does retry preserve scroll position? does refresh clear
/// the error first?) turns into fifteen different small inconsistencies.
class AsyncList<T> extends StatefulWidget {
  const AsyncList({
    super.key,
    required this.loader,
    required this.itemBuilder,
    this.emptyIcon = Icons.inbox_outlined,
    this.emptyText = 'Nothing here yet.',
    this.header,
  });

  final Future<List<T>> Function() loader;
  final Widget Function(BuildContext, T) itemBuilder;
  final IconData emptyIcon;
  final String emptyText;
  final Widget? header;

  @override
  State<AsyncList<T>> createState() => AsyncListState<T>();
}

class AsyncListState<T> extends State<AsyncList<T>> {
  List<T>? _items;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    reload();
  }

  Future<void> reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await widget.loader();
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

  @override
  Widget build(BuildContext context) {
    if (_loading && _items == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _items == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 40, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            TextButton(onPressed: reload, child: const Text('Try again')),
          ],
        ),
      );
    }

    final items = _items ?? const [];
    return RefreshIndicator(
      onRefresh: reload,
      child: items.isEmpty
          ? ListView(
              children: [
                if (widget.header != null) widget.header!,
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 64),
                  child: Center(
                    child: Column(
                      children: [
                        Icon(widget.emptyIcon,
                            size: 40, color: Theme.of(context).colorScheme.outline),
                        const SizedBox(height: 12),
                        Text(widget.emptyText),
                      ],
                    ),
                  ),
                ),
              ],
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: items.length + (widget.header != null ? 1 : 0),
              itemBuilder: (context, i) {
                if (widget.header != null) {
                  if (i == 0) return widget.header!;
                  return widget.itemBuilder(context, items[i - 1]);
                }
                return widget.itemBuilder(context, items[i]);
              },
            ),
    );
  }
}

/// A small status pill — `Card`/`ListTile` trailing widgets across contracts,
/// orders, proposals, and challenges all want the same shape.
class StatusPill extends StatelessWidget {
  const StatusPill(this.label, {super.key, this.color});

  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final c = color ?? scheme.outline;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: TextStyle(fontSize: 12, color: c)),
    );
  }
}

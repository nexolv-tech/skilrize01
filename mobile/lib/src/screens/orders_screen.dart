import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/gigs.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

class OrdersScreen extends StatelessWidget {
  const OrdersScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Orders')),
      body: AsyncList<GigOrder>(
        loader: () async => (await session.api.orders()).results,
        emptyIcon: Icons.shopping_bag_outlined,
        emptyText: 'No orders yet.',
        itemBuilder: (context, order) => Card(
          margin: const EdgeInsets.only(bottom: 10),
          child: ListTile(
            title: Text(order.gigTitle),
            subtitle: Text(
              '${order.myRole == 'buyer' ? order.sellerName : order.buyerName} · Rs ${order.price}',
            ),
            trailing: StatusPill(order.status),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => OrderDetailScreen(session: session, orderId: order.id),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class OrderDetailScreen extends StatefulWidget {
  const OrderDetailScreen({super.key, required this.session, required this.orderId});
  final Session session;
  final int orderId;

  @override
  State<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends State<OrderDetailScreen> {
  GigOrder? _order;
  String? _error;
  bool _busy = false;
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final order = await widget.session.api.order(widget.orderId);
      if (!mounted) return;
      setState(() => _order = order);
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _act(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
      await _load();
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final order = _order;
    return Scaffold(
      appBar: AppBar(title: Text(order?.gigTitle ?? 'Order')),
      body: order == null
          ? Center(child: Text(_error ?? ''))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Rs ${order.price}', style: Theme.of(context).textTheme.titleLarge),
                    StatusPill(order.status),
                  ],
                ),
                const SizedBox(height: 8),
                Text('${order.revisionsLeft} revisions left'),
                const SizedBox(height: 20),
                if (order.myRole == 'seller' && order.status == 'active') ...[
                  TextField(
                    controller: _note,
                    maxLines: 3,
                    decoration: const InputDecoration(labelText: 'Delivery note'),
                  ),
                  const SizedBox(height: 10),
                  FilledButton(
                    onPressed: _busy
                        ? null
                        : () => _act(() =>
                            widget.session.api.deliverOrder(order.id, _note.text.trim())),
                    child: const Text('Deliver'),
                  ),
                ],
                if (order.myRole == 'buyer' && order.status == 'delivered') ...[
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton(
                          onPressed: _busy
                              ? null
                              : () => _act(() => widget.session.api.acceptOrder(order.id)),
                          child: const Text('Accept delivery'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      if (order.revisionsLeft > 0)
                        Expanded(
                          child: OutlinedButton(
                            onPressed: _busy
                                ? null
                                : () => _act(() => widget.session.api
                                    .requestRevision(order.id, _note.text.trim())),
                            child: const Text('Request revision'),
                          ),
                        ),
                    ],
                  ),
                ],
              ],
            ),
    );
  }
}

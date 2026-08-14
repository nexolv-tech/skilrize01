import 'package:flutter/material.dart';

import '../state/session.dart';
import 'contracts_screen.dart';
import 'dashboard_screen.dart';
import 'notifications_screen.dart';
import 'projects_screen.dart';

/// The signed-in shell: four destinations, which is the honest shape of a
/// phone client for this product. The web app's twenty-odd routes exist
/// because a desktop nav can hold them; a bottom bar cannot, and pretending
/// otherwise is how mobile ports become unusable.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.session});

  final Session session;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final screens = [
      DashboardScreen(session: session),
      ProjectsScreen(session: session),
      ContractsScreen(session: session),
      NotificationsScreen(session: session),
    ];

    return Scaffold(
      body: IndexedStack(index: _index, children: screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.work_outline), label: 'Projects'),
          NavigationDestination(icon: Icon(Icons.description_outlined), label: 'Contracts'),
          NavigationDestination(icon: Icon(Icons.notifications_outlined), label: 'Alerts'),
        ],
      ),
    );
  }
}

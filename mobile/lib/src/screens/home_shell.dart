import 'package:flutter/material.dart';

import '../state/session.dart';
import 'contracts_screen.dart';
import 'dashboard_screen.dart';
import 'messages_screen.dart';
import 'more_screen.dart';
import 'work_hub_screen.dart';

/// The signed-in shell.
///
/// Five bottom-nav destinations, not the web app's ~35 routes — a phone nav
/// bar cannot hold that many and pretending otherwise is how mobile ports
/// become unusable. Home/Work/Messages/Contracts cover the everyday loop;
/// everything else (professional layer, integrations, settings, admin,
/// student verification, feed) lives one tap deeper under [MoreScreen],
/// mirroring how the web app itself separates "the work" from "the account".
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
      WorkHubScreen(session: session),
      MessagesScreen(session: session),
      ContractsScreen(session: session),
      MoreScreen(session: session),
    ];

    return Scaffold(
      body: IndexedStack(index: _index, children: screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.work_outline), label: 'Work'),
          NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: 'Messages'),
          NavigationDestination(icon: Icon(Icons.description_outlined), label: 'Contracts'),
          NavigationDestination(icon: Icon(Icons.more_horiz), label: 'More'),
        ],
      ),
    );
  }
}

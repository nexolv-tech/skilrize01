import 'package:flutter/material.dart';

import '../models/gigs.dart';
import '../models/models.dart';
import '../state/session.dart';
import 'gigs_screen.dart';
import 'project_detail_screen.dart';

/// One search box, two result kinds — gigs and projects share the same
/// query the way `discovery.searchGigs`/`searchProjects` share a filter
/// shape server-side. A segmented control picks which the list shows.
class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key, required this.session});
  final Session session;

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

enum _Kind { gigs, projects }

class _SearchScreenState extends State<SearchScreen> {
  final _query = TextEditingController();
  _Kind _kind = _Kind.gigs;
  List<GigSummary>? _gigResults;
  List<ProjectSummary>? _projectResults;
  bool _loading = false;

  Future<void> _search() async {
    setState(() => _loading = true);
    try {
      if (_kind == _Kind.gigs) {
        final page = await widget.session.api.gigs(search: _query.text.trim());
        if (mounted) setState(() => _gigResults = page.results);
      } else {
        final page = await widget.session.api.projects(search: _query.text.trim());
        if (mounted) setState(() => _projectResults = page.results);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Search')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                TextField(
                  controller: _query,
                  textInputAction: TextInputAction.search,
                  onSubmitted: (_) => _search(),
                  decoration: InputDecoration(
                    hintText: 'Search',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon:
                        IconButton(icon: const Icon(Icons.arrow_forward), onPressed: _search),
                  ),
                ),
                const SizedBox(height: 10),
                SegmentedButton<_Kind>(
                  segments: const [
                    ButtonSegment(value: _Kind.gigs, label: Text('Gigs')),
                    ButtonSegment(value: _Kind.projects, label: Text('Projects')),
                  ],
                  selected: {_kind},
                  onSelectionChanged: (s) {
                    setState(() => _kind = s.first);
                    _search();
                  },
                ),
              ],
            ),
          ),
          if (_loading) const LinearProgressIndicator(),
          Expanded(
            child: _kind == _Kind.gigs
                ? ListView(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    children: [
                      for (final gig in _gigResults ?? const [])
                        Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            title: Text(gig.title),
                            subtitle: Text('from Rs ${gig.startingPrice}'),
                            onTap: () => Navigator.of(context).push(MaterialPageRoute(
                              builder: (_) =>
                                  GigDetailScreen(session: widget.session, gigId: gig.id),
                            )),
                          ),
                        ),
                    ],
                  )
                : ListView(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    children: [
                      for (final project in _projectResults ?? const [])
                        Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            title: Text(project.title),
                            subtitle: Text(project.budgetDisplay),
                            onTap: () => Navigator.of(context).push(MaterialPageRoute(
                              builder: (_) => ProjectDetailScreen(
                                  session: widget.session, projectId: project.id),
                            )),
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

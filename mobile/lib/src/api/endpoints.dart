import '../models/models.dart';
import 'client.dart';

/// Typed wrappers over the endpoints this client actually uses.
///
/// Grouped by the API app they belong to, mirroring `web/lib/api.ts` so the
/// two clients stay recognisably the same product. Anything not listed here
/// is not something the app calls — the surface is deliberately a slice, not
/// a mirror of all 40-odd routes.
class SkilrizeApi {
  SkilrizeApi(this.client);

  final ApiClient client;

  // --- Bootstrap ------------------------------------------------------------

  /// What this deployment supports. `push_enabled` is the one that matters
  /// on mobile: asking for the OS notification permission on a deployment
  /// that cannot deliver a push spends the single prompt the platform grants
  /// for nothing (`core/views.py`, Phase 7).
  Future<Map<String, dynamic>> config() async {
    final data = await client.get('/config/');
    return Map<String, dynamic>.from(data as Map);
  }

  // --- Auth -----------------------------------------------------------------

  Future<Map<String, dynamic>> login(String email, String password) async {
    final data = await client.post('/auth/login/', {'email': email, 'password': password});
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> loginTwoFactor(String challenge, String code) async {
    final data = await client.post('/auth/login/2fa/', {'challenge': challenge, 'code': code});
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> loginVerifyDevice(String challenge, String code) async {
    final data = await client.post('/auth/login/device/', {'challenge': challenge, 'code': code});
    return Map<String, dynamic>.from(data as Map);
  }

  Future<User> me() async => User.fromJson(Map<String, dynamic>.from(await client.get('/auth/me/') as Map));

  Future<void> logout(String? refreshToken) =>
      client.post('/auth/logout/', {if (refreshToken != null) 'refresh': refreshToken});

  // --- Marketplace ----------------------------------------------------------

  Future<Paginated<ProjectSummary>> projects({String? search, int page = 1}) async {
    final data = await client.get('/projects/', {
      'page': '$page',
      if (search != null && search.isNotEmpty) 'search': search,
    });
    return Paginated.from(Map<String, dynamic>.from(data as Map), ProjectSummary.fromJson);
  }

  // --- Contracts ------------------------------------------------------------

  Future<Paginated<ContractSummary>> contracts({String? role, int page = 1}) async {
    final data = await client.get('/contracts/', {
      'page': '$page',
      if (role != null && role.isNotEmpty) 'role': role,
    });
    return Paginated.from(Map<String, dynamic>.from(data as Map), ContractSummary.fromJson);
  }

  Future<ContractDetail> contract(int id) async =>
      ContractDetail.fromJson(Map<String, dynamic>.from(await client.get('/contracts/$id/') as Map));

  // --- Notifications --------------------------------------------------------

  /// Returns a bare list, not a page.
  ///
  /// `NotificationListView` is the one list endpoint in the API that does not
  /// set `pagination_class`, so DRF answers with a plain JSON array rather
  /// than the `{count, next, results}` envelope every other list uses. Found
  /// by the live suite — the mocked tests happily returned whichever shape
  /// they were told to.
  Future<List<AppNotification>> notifications({bool unreadOnly = false}) async {
    final data = await client.get('/notifications/', {
      if (unreadOnly) 'unread': 'true',
    });
    return (data as List)
        .map((e) => AppNotification.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<int> markNotificationsRead({List<int>? ids}) async {
    final data = await client.post('/notifications/read/', {if (ids != null) 'ids': ids});
    return (data as Map)['updated'] as int? ?? 0;
  }

  // --- Push devices (Phase 7) ----------------------------------------------

  Future<void> registerPushDevice({
    required String token,
    required String platform,
    String label = '',
  }) =>
      client.post('/devices/push/', {
        'token': token,
        'platform': platform,
        if (label.isNotEmpty) 'label': label,
      });

  Future<void> unregisterPushDevice(String token) =>
      client.post('/devices/push/unregister/', {'token': token});
}

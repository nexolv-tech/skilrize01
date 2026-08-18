import '../models/communities.dart';
import '../models/gigs.dart';
import '../models/marketplace.dart';
import '../models/messaging.dart';
import '../models/misc.dart';
import '../models/models.dart';
import '../models/payments.dart';
import '../models/professional.dart';
import 'client.dart';

/// Typed wrappers over every endpoint the app uses, grouped by the API app
/// each belongs to — mirrors `web/lib/api.ts`'s own grouping so the two
/// clients read as the same product from two directions.
class SkilrizeApi {
  SkilrizeApi(this.client);

  final ApiClient client;

  Map<String, dynamic> _map(Object? data) => Map<String, dynamic>.from(data as Map);
  List<Map<String, dynamic>> _list(Object? data) =>
      (data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();

  // --- Bootstrap --------------------------------------------------------

  Future<Map<String, dynamic>> config() async => _map(await client.get('/config/'));

  // --- Auth ---------------------------------------------------------------

  Future<Map<String, dynamic>> login(String email, String password) async =>
      _map(await client.post('/auth/login/', {'email': email, 'password': password}));

  Future<Map<String, dynamic>> loginTwoFactor(String challenge, String code) async =>
      _map(await client.post('/auth/login/2fa/', {'challenge': challenge, 'code': code}));

  Future<Map<String, dynamic>> loginVerifyDevice(String challenge, String code) async =>
      _map(await client.post('/auth/login/device/', {'challenge': challenge, 'code': code}));

  Future<Map<String, dynamic>> loginTwoFactorEnrolSetup(String challenge) async =>
      _map(await client.post('/auth/login/2fa/enrol/setup/', {'challenge': challenge}));

  Future<Map<String, dynamic>> loginTwoFactorEnrolConfirm(String challenge, String code) async =>
      _map(await client
          .post('/auth/login/2fa/enrol/confirm/', {'challenge': challenge, 'code': code}));

  Future<User> me() async => User.fromJson(_map(await client.get('/auth/me/')));

  Future<User> updateMe(Map<String, dynamic> patch) async =>
      User.fromJson(_map(await client.patch('/auth/me/', patch)));

  Future<void> logout(String? refreshToken) =>
      client.post('/auth/logout/', {if (refreshToken != null) 'refresh': refreshToken});

  Future<void> requestPasswordReset(String email) =>
      client.post('/auth/password/reset/', {'email': email});

  Future<Map<String, dynamic>> changePassword(String current, String next) async => _map(
        await client.post('/auth/password/change/', {
          'current_password': current,
          'new_password': next,
        }),
      );

  Future<List<AuthSession>> sessions() async =>
      _list(await client.get('/auth/sessions/')).map(AuthSession.fromJson).toList();

  Future<void> revokeSession(String family) => client.delete('/auth/sessions/$family/');
  Future<void> revokeAllSessions() => client.post('/auth/sessions/revoke-all/');

  Future<Map<String, dynamic>> twoFactorSetup() async =>
      _map(await client.post('/auth/2fa/setup/'));

  Future<List<String>> twoFactorConfirm(String code) async {
    final data = _map(await client.post('/auth/2fa/confirm/', {'code': code}));
    return ((data['recovery_codes'] as List?) ?? const []).map((e) => '$e').toList();
  }

  Future<void> twoFactorDisable({String? password, String? code}) => client.post(
        '/auth/2fa/disable/',
        {if (password != null) 'password': password, if (code != null) 'code': code},
      );

  // --- Student verification ------------------------------------------------

  Future<StudentApplication?> studentApplication() async {
    final data = _map(await client.get('/auth/student/'));
    return data['application'] == null
        ? null
        : StudentApplication.fromJson(_map(data['application']));
  }

  Future<Map<String, dynamic>> lookupUniversity(String email) async =>
      _map(await client.get('/auth/universities/lookup/', {'email': email}));

  Future<StudentApplication> startStudentVerification(String universityEmail) async {
    final data =
        await client.post('/auth/student/email/', {'university_email': universityEmail});
    return StudentApplication.fromJson(_map(_map(data)['application']));
  }

  Future<StudentApplication> confirmStudentEmail(String code) async {
    final data = await client.post('/auth/student/email/verify/', {'code': code});
    return StudentApplication.fromJson(_map(_map(data)['application']));
  }

  Future<StudentApplication> uploadStudentIdCard(List<int> bytes, String filename) async {
    final data = await client.uploadFile('/auth/student/id-card/', 'file', bytes, filename);
    return StudentApplication.fromJson(_map(_map(data)['application']));
  }

  // --- Marketplace ----------------------------------------------------------

  Future<List<Category>> categories() async =>
      _list(await client.get('/categories/')).map(Category.fromJson).toList();

  Future<List<Skill>> skills({String? q}) async =>
      _list(await client.get('/skills/', {if (q != null) 'q': q})).map(Skill.fromJson).toList();

  Future<Paginated<ProjectSummary>> projects({String? search, int page = 1}) async {
    final data = await client.get('/projects/', {
      'page': '$page',
      if (search != null && search.isNotEmpty) 'search': search,
    });
    return Paginated.from(_map(data), ProjectSummary.fromJson);
  }

  Future<ProjectDetail> project(int id) async =>
      ProjectDetail.fromJson(_map(await client.get('/projects/$id/')));

  Future<Proposal> submitProposal(int projectId, Map<String, dynamic> body) async =>
      Proposal.fromJson(_map(await client.post('/projects/$projectId/proposals/', body)));

  Future<Paginated<Proposal>> myProposals({String? status, int page = 1}) async {
    final data = await client.get('/proposals/', {
      'page': '$page',
      if (status != null && status.isNotEmpty) 'status': status,
    });
    return Paginated.from(_map(data), Proposal.fromJson);
  }

  Future<void> withdrawProposal(int id) => client.post('/proposals/$id/withdraw/');

  Future<Trial> proposeTrial(int proposalId, Map<String, dynamic> body) async =>
      Trial.fromJson(_map(await client.post('/proposals/$proposalId/trial/', body)));

  Future<Map<String, dynamic>> acceptTrial(int proposalId) async =>
      _map(await client.post('/proposals/$proposalId/trial/accept/'));

  Future<void> declineTrial(int proposalId) => client.post('/proposals/$proposalId/trial/decline/');

  Future<ContractDetail> convertTrial(int proposalId) async =>
      ContractDetail.fromJson(_map(await client.post('/proposals/$proposalId/trial/convert/')));

  // --- Contracts (extends the read-only set already in the app) -----------

  Future<Paginated<ContractSummary>> contracts({String? role, int page = 1}) async {
    final data = await client.get('/contracts/', {
      'page': '$page',
      if (role != null && role.isNotEmpty) 'role': role,
    });
    return Paginated.from(_map(data), ContractSummary.fromJson);
  }

  Future<ContractDetail> contract(int id) async =>
      ContractDetail.fromJson(_map(await client.get('/contracts/$id/')));

  Future<ContractDetail> awardContract(int proposalId) async =>
      ContractDetail.fromJson(_map(await client.post('/contracts/award/', {'proposal': proposalId})));

  Future<ContractDetail> acceptContract(int id) async =>
      ContractDetail.fromJson(_map(await client.post('/contracts/$id/accept/')));

  /// **Money-moving — `CanMoveMoney`.** Marks a milestone funded — the
  /// client has already transferred the money to the platform's own bank
  /// account (`bankTransferInstructions()`) and this call is them
  /// confirming that (Phase 3, D42). Can raise `ApiError` with code
  /// `profile_incomplete`, `device_cooloff`, or `two_factor_required`;
  /// callers should route those through `MoneyGateBanner`.
  Future<ContractDetail> fundMilestone(
    int contractId,
    int milestoneId, {
    String referenceNote = '',
  }) async =>
      ContractDetail.fromJson(_map(await client.post(
        '/contracts/$contractId/milestones/$milestoneId/fund/',
        {'reference_note': referenceNote},
      )));

  /// **Money-moving — `CanMoveMoney`.**
  Future<ContractDetail> releaseMilestone(int contractId, int milestoneId) async =>
      ContractDetail.fromJson(
        _map(await client.post('/contracts/$contractId/milestones/$milestoneId/release/')),
      );

  Future<List<Map<String, dynamic>>> contractEvents(int id) async =>
      _list(await client.get('/contracts/$id/events/'));

  Future<Map<String, dynamic>> postContractMessage(int id, String body) async =>
      _map(await client.post('/contracts/$id/events/', {'body': body}));

  Future<List<Map<String, dynamic>>> timeEntries(int id) async =>
      _list(await client.get('/contracts/$id/time/'));

  Future<void> logTime(int id, {required String workedOn, required int minutes, String memo = ''}) =>
      client.post('/contracts/$id/time/', {
        'worked_on': workedOn,
        'minutes': minutes,
        'memo': memo,
      });

  Future<void> submitReview(int contractId, Map<String, dynamic> body) =>
      client.post('/contracts/$contractId/review/', body);

  // --- Gigs & orders --------------------------------------------------------

  Future<Paginated<GigSummary>> gigs({String? search, int page = 1}) async {
    final data = await client.get('/gigs/', {
      'page': '$page',
      if (search != null && search.isNotEmpty) 'search': search,
    });
    return Paginated.from(_map(data), GigSummary.fromJson);
  }

  Future<GigDetail> gig(int id) async => GigDetail.fromJson(_map(await client.get('/gigs/$id/')));

  /// **Money-moving — `CanMoveMoney`.** Paid up front, the same trust
  /// basis as `fundMilestone` — the buyer has already transferred payment
  /// to the platform's own bank account (Phase 3, D42).
  Future<GigOrder> orderGig(
    int gigId, {
    required int package,
    List<int>? extras,
    String referenceNote = '',
  }) async {
    final data = await client.post('/gigs/$gigId/order/', {
      'package': package,
      if (extras != null) 'extras': extras,
      'reference_note': referenceNote,
    });
    return GigOrder.fromJson(_map(data));
  }

  Future<Paginated<GigOrder>> orders({String? role, int page = 1}) async {
    final data = await client.get('/orders/', {
      'page': '$page',
      if (role != null) 'role': role,
    });
    return Paginated.from(_map(data), GigOrder.fromJson);
  }

  Future<GigOrder> order(int id) async => GigOrder.fromJson(_map(await client.get('/orders/$id/')));

  Future<void> deliverOrder(int id, String note) =>
      client.post('/orders/$id/deliver/', {'note': note});

  Future<void> requestRevision(int id, String note) =>
      client.post('/orders/$id/request-revision/', {'note': note});

  Future<void> acceptOrder(int id) => client.post('/orders/$id/accept/');

  // --- Messaging --------------------------------------------------------

  Future<Paginated<Conversation>> conversations({int page = 1}) async {
    final data = await client.get('/conversations/', {'page': '$page'});
    return Paginated.from(_map(data), Conversation.fromJson);
  }

  Future<Conversation> startConversation(String handle) async =>
      Conversation.fromJson(_map(await client.post('/conversations/start/', {'handle': handle})));

  Future<Paginated<DirectMessage>> thread(int conversationId, {int page = 1}) async {
    final data = await client.get('/conversations/$conversationId/messages/', {'page': '$page'});
    return Paginated.from(_map(data), DirectMessage.fromJson);
  }

  Future<DirectMessage> sendMessage(int conversationId, String body) async =>
      DirectMessage.fromJson(
        _map(await client.post('/conversations/$conversationId/messages/', {'body': body})),
      );

  // --- Communities --------------------------------------------------------

  Future<Paginated<Community>> communities({int page = 1}) async {
    final data = await client.get('/communities/', {'page': '$page'});
    return Paginated.from(_map(data), Community.fromJson);
  }

  Future<Community> community(int id) async =>
      Community.fromJson(_map(await client.get('/communities/$id/')));

  Future<void> joinCommunity(int id) => client.post('/communities/$id/join/');
  Future<void> leaveCommunity(int id) => client.post('/communities/$id/leave/');

  Future<Paginated<CommunityThread>> threads(int communityId, {int page = 1}) async {
    final data = await client.get('/threads/', {'community': '$communityId', 'page': '$page'});
    return Paginated.from(_map(data), CommunityThread.fromJson);
  }

  Future<Paginated<ThreadReply>> threadReplies(int threadId, {int page = 1}) async {
    final data = await client.get('/threads/$threadId/replies/', {'page': '$page'});
    return Paginated.from(_map(data), ThreadReply.fromJson);
  }

  Future<void> reply(int threadId, String body) =>
      client.post('/threads/$threadId/replies/', {'body': body});

  Future<List<ChatMessage>> chat(int communityId, {String? before}) async {
    final data = await client
        .get('/communities/$communityId/chat/', {if (before != null) 'before': before});
    return _list(data).map(ChatMessage.fromJson).toList();
  }

  Future<ChatMessage> sendChat(int communityId, String body) async => ChatMessage.fromJson(
        _map(await client.post('/communities/$communityId/chat/', {'body': body})),
      );

  Future<Paginated<CommunityEvent>> communityEvents({int? communityId, int page = 1}) async {
    final data = await client.get(
      '/events/',
      {'page': '$page', if (communityId != null) 'community': '$communityId'},
    );
    return Paginated.from(_map(data), CommunityEvent.fromJson);
  }

  Future<void> rsvp(int eventId, String response) =>
      client.post('/events/$eventId/rsvp/', {'response': response});

  Future<Paginated<CommunityResource>> resources({int? communityId, int page = 1}) async {
    final data = await client.get(
      '/resources/',
      {'page': '$page', if (communityId != null) 'community': '$communityId'},
    );
    return Paginated.from(_map(data), CommunityResource.fromJson);
  }

  Future<Paginated<FeedEntry>> feed({String? verb, int page = 1}) async {
    final data =
        await client.get('/feed/', {'page': '$page', if (verb != null) 'verb': verb});
    return Paginated.from(_map(data), FeedEntry.fromJson);
  }

  // --- Discovery ------------------------------------------------------------

  Future<Paginated<ShowcasePiece>> showcase({int page = 1}) async {
    final data = await client.get('/showcase/', {'page': '$page'});
    return Paginated.from(_map(data), ShowcasePiece.fromJson);
  }

  // --- Professional -----------------------------------------------------

  Future<List<SubscriptionPlan>> plans() async =>
      _list(await client.get('/plans/')).map(SubscriptionPlan.fromJson).toList();

  Future<Entitlements> entitlements() async {
    final data = _map(await client.get('/subscription/'));
    return Entitlements.fromJson(_map(data['entitlements']));
  }

  /// Switching to Free needs no `referenceNote` — nothing is being paid
  /// for. A paid tier is **money-moving — `CanMoveMoney`**, the same trust
  /// basis `fundMilestone`/`orderGig` run on: the caller has already
  /// transferred the plan's price to the platform's own bank account
  /// (Phase 3, D42) and this call is them confirming that.
  Future<void> subscribe(String tier, String interval, {String referenceNote = ''}) =>
      client.post('/subscription/subscribe/', {
        'tier': tier,
        'interval': interval,
        'reference_note': referenceNote,
      });

  Future<Paginated<CrmContact>> crmContacts({int page = 1}) async {
    final data = await client.get('/crm/contacts/', {'page': '$page'});
    return Paginated.from(_map(data), CrmContact.fromJson);
  }

  /// Can raise 402 `upgrade_required` when the plan's contact limit is hit.
  Future<CrmContact> createCrmContact(Map<String, dynamic> body) async =>
      CrmContact.fromJson(_map(await client.post('/crm/contacts/', body)));

  Future<Paginated<CrmDeal>> crmDeals({int page = 1}) async {
    final data = await client.get('/crm/deals/', {'page': '$page'});
    return Paginated.from(_map(data), CrmDeal.fromJson);
  }

  Future<void> moveDeal(int id, String stage) =>
      client.post('/crm/deals/$id/stage/', {'stage': stage});

  Future<Paginated<CrmTask>> crmTasks({int page = 1}) async {
    final data = await client.get('/crm/tasks/', {'page': '$page'});
    return Paginated.from(_map(data), CrmTask.fromJson);
  }

  Future<void> toggleCrmTask(int id) => client.post('/crm/tasks/$id/complete/');

  Future<Paginated<AgencyTeam>> agencies({int page = 1}) async {
    final data = await client.get('/agencies/', {'page': '$page'});
    return Paginated.from(_map(data), AgencyTeam.fromJson);
  }

  /// Can raise 402 `upgrade_required` — creating an agency needs an Elite plan.
  Future<AgencyTeam> createAgency(String name) async =>
      AgencyTeam.fromJson(_map(await client.post('/agencies/', {'name': name})));

  Future<Paginated<SharedWorkspace>> workspaces({int page = 1}) async {
    final data = await client.get('/workspaces/', {'page': '$page'});
    return Paginated.from(_map(data), SharedWorkspace.fromJson);
  }

  Future<Paginated<Retainer>> retainers({int page = 1}) async {
    final data = await client.get('/retainers/', {'page': '$page'});
    return Paginated.from(_map(data), Retainer.fromJson);
  }

  /// Can raise 402 `upgrade_required` — selling retainers needs Pro or Elite.
  Future<Retainer> createRetainer(Map<String, dynamic> body) async =>
      Retainer.fromJson(_map(await client.post('/retainers/', body)));

  Future<void> subscribeToRetainer(int id) => client.post('/retainers/$id/subscribe/');

  // --- Challenges ---------------------------------------------------------

  Future<Paginated<Challenge>> challenges({int page = 1}) async {
    final data = await client.get('/challenges/', {'page': '$page'});
    return Paginated.from(_map(data), Challenge.fromJson);
  }

  Future<Challenge> challenge(String slug) async =>
      Challenge.fromJson(_map(await client.get('/challenges/$slug/')));

  Future<ChallengeParticipation> joinChallenge(String slug) async =>
      ChallengeParticipation.fromJson(_map(await client.post('/challenges/$slug/join/')));

  Future<ChallengeParticipation> submitChallenge(
    String slug, {
    required String submissionUrl,
    String repoUrl = '',
    String notes = '',
  }) async =>
      ChallengeParticipation.fromJson(_map(await client.post('/challenges/$slug/submit/', {
        'submission_url': submissionUrl,
        if (repoUrl.isNotEmpty) 'repo_url': repoUrl,
        if (notes.isNotEmpty) 'notes': notes,
      })));

  Future<List<ChallengeParticipation>> myChallenges() async =>
      _list(await client.get('/challenges/mine/')).map(ChallengeParticipation.fromJson).toList();

  // --- Integrations ---------------------------------------------------------

  Future<List<ProviderStatus>> providers() async =>
      _list(await client.get('/integrations/providers/')).map(ProviderStatus.fromJson).toList();

  Future<Map<String, dynamic>> authorizeProvider(String provider) async =>
      _map(await client.get('/integrations/$provider/authorize/'));

  Future<void> disconnectProvider(String provider) =>
      client.delete('/integrations/$provider/disconnect/');

  Future<List<ContractMeeting>> meetings(int contractId) async =>
      _list(await client.get('/contracts/$contractId/meetings/')).map(ContractMeeting.fromJson).toList();

  Future<ContractMeeting> scheduleMeeting(
    int contractId, {
    required String provider,
    required String topic,
    required String startTime,
    int durationMinutes = 30,
  }) async =>
      ContractMeeting.fromJson(_map(await client.post('/contracts/$contractId/meetings/', {
        'provider': provider,
        'topic': topic,
        'start_time': startTime,
        'duration_minutes': durationMinutes,
      })));

  Future<void> cancelMeeting(int meetingId) => client.post('/meetings/$meetingId/cancel/');

  Future<List<ActivitySource>> activitySources(int contractId) async =>
      _list(await client.get('/contracts/$contractId/activity-sources/'))
          .map(ActivitySource.fromJson)
          .toList();

  Future<void> addActivitySource(int contractId, {required String provider, required String ref}) =>
      client.post('/contracts/$contractId/activity-sources/', {
        'provider': provider,
        'external_ref': ref,
      });

  Future<void> syncActivitySource(int sourceId) =>
      client.post('/activity-sources/$sourceId/sync/');

  // --- Admin (role-gated server-side) ---------------------------------------

  Future<Paginated<AdminVerification>> adminVerifications({String? status, int page = 1}) async {
    final data = await client.get(
      '/auth/admin/verifications/',
      {'page': '$page', if (status != null) 'status': status},
    );
    return Paginated.from(_map(data), AdminVerification.fromJson);
  }

  Future<void> approveVerification(int id) =>
      client.post('/auth/admin/verifications/$id/approve/');

  Future<void> rejectVerification(int id, String reason) =>
      client.post('/auth/admin/verifications/$id/reject/', {'reason': reason});

  Future<Paginated<AdminUserRow>> adminUsers({String? q, int page = 1}) async {
    final data =
        await client.get('/auth/admin/users/', {'page': '$page', if (q != null) 'q': q});
    return Paginated.from(_map(data), AdminUserRow.fromJson);
  }

  Future<void> suspendUser(int id, String reason) =>
      client.post('/auth/admin/users/$id/suspend/', {'reason': reason});

  Future<void> reactivateUser(int id) => client.post('/auth/admin/users/$id/reactivate/');

  Future<Paginated<AuditLogEntry>> auditLog({int page = 1}) async {
    final data = await client.get('/auth/admin/audit-log/', {'page': '$page'});
    return Paginated.from(_map(data), AuditLogEntry.fromJson);
  }

  // --- Payments (Phase 3, D42) -------------------------------------------

  /// Where to actually send money to fund a milestone or order — the one
  /// piece of real payment infrastructure this phase has: the platform's
  /// own bank account.
  Future<BankTransferInstructions> bankTransferInstructions() async =>
      BankTransferInstructions.fromJson(
        _map(await client.get('/payments/bank-transfer-instructions/')),
      );

  Future<PayoutProfile> payoutProfile() async =>
      PayoutProfile.fromJson(_map(await client.get('/payments/payout-profile/')));

  /// **Money-adjacent — `CanMoveMoney`.** Where released funds go is exactly
  /// the kind of account change that gate exists for.
  Future<PayoutProfile> savePayoutProfile({
    required String bankName,
    required String accountTitle,
    required String accountNumber,
    required String cnic,
    required String msisdn,
  }) async {
    final data = await client.patch('/payments/payout-profile/', {
      'bank_name': bankName,
      'account_title': accountTitle,
      'account_number': accountNumber,
      'cnic': cnic,
      'msisdn': msisdn,
    });
    return PayoutProfile.fromJson(_map(data));
  }

  Future<Paginated<Payout>> myPayouts({int page = 1}) async {
    final data = await client.get('/payments/payouts/', {'page': '$page'});
    return Paginated.from(_map(data), Payout.fromJson);
  }

  // --- Notifications & push (existing) --------------------------------------

  Future<List<AppNotification>> notifications({bool unreadOnly = false}) async {
    final data = await client.get('/notifications/', {if (unreadOnly) 'unread': 'true'});
    return (data as List)
        .map((e) => AppNotification.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<int> markNotificationsRead({List<int>? ids}) async {
    final data = await client.post('/notifications/read/', {if (ids != null) 'ids': ids});
    return (data as Map)['updated'] as int? ?? 0;
  }

  Future<Map<String, dynamic>> notificationPreferences() async =>
      _map(await client.get('/notifications/preferences/'));

  Future<Map<String, dynamic>> updateNotificationPreferences(Map<String, dynamic> patch) async =>
      _map(await client.patch('/notifications/preferences/', patch));

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

import 'package:flutter/material.dart';

import '../api/api_error.dart';

/// What a money-adjacent action was refused for.
///
/// Three distinct 403 codes from `CanTransact`/`CanMoveMoney`
/// (`accounts/auth.py`), plus the unrelated 402 `upgrade_required` from
/// `professional/views.py`'s plan-entitlement checks. They read as the same
/// shape of failure ("you can't do that yet") but need different next
/// actions, so the UI has to branch on the code, not just show the message.
enum MoneyGateReason {
  profileIncomplete,
  deviceCooloff,
  twoFactorRequired,
  upgradeRequired,

  /// Anything else — shown as a plain error, no special next step.
  other,
}

MoneyGateReason moneyGateReasonFor(ApiError error) => switch (error.code) {
      'profile_incomplete' => MoneyGateReason.profileIncomplete,
      'device_cooloff' => MoneyGateReason.deviceCooloff,
      'two_factor_required' => MoneyGateReason.twoFactorRequired,
      'upgrade_required' => MoneyGateReason.upgradeRequired,
      _ => MoneyGateReason.other,
    };

/// A banner explaining why a money action was refused, with the one button
/// that actually unblocks it — sending someone to "contact support" for a
/// `device_cooloff` they just need to wait out is worse than saying nothing.
class MoneyGateBanner extends StatelessWidget {
  const MoneyGateBanner({
    super.key,
    required this.error,
    this.onCompleteProfile,
    this.onSetUpTwoFactor,
    this.onUpgrade,
  });

  final ApiError error;
  final VoidCallback? onCompleteProfile;
  final VoidCallback? onSetUpTwoFactor;
  final VoidCallback? onUpgrade;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final reason = moneyGateReasonFor(error);

    final (title, action) = switch (reason) {
      MoneyGateReason.profileIncomplete => (
          'Finish setting up your account',
          onCompleteProfile != null
              ? TextButton(onPressed: onCompleteProfile, child: const Text('Complete profile'))
              : null,
        ),
      MoneyGateReason.deviceCooloff => ('New device — one moment', null),
      MoneyGateReason.twoFactorRequired => (
          'Two-factor authentication required',
          onSetUpTwoFactor != null
              ? TextButton(onPressed: onSetUpTwoFactor, child: const Text('Set up 2FA'))
              : null,
        ),
      MoneyGateReason.upgradeRequired => (
          'Your plan doesn\'t include this',
          onUpgrade != null
              ? TextButton(onPressed: onUpgrade, child: const Text('View plans'))
              : null,
        ),
      MoneyGateReason.other => ('Something went wrong', null),
    };

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(fontWeight: FontWeight.w600, color: scheme.onErrorContainer)),
          const SizedBox(height: 4),
          Text(error.message, style: TextStyle(color: scheme.onErrorContainer)),
          if (action != null) action,
        ],
      ),
    );
  }
}

/**
 * Who operates SkilRize, stated once.
 *
 * Payment networks and card acquirers require a merchant's website to show
 * the legal operator, a physical business address and working contact
 * details, and every legal page names the data controller. They all read from
 * here, so changing an address or phone number is one edit — and a
 * redeploy, since these are compiled into the static pages.
 */
export const BUSINESS = {
  product: "SkilRize",
  /** The legal operator: a sole proprietorship registered with the FBR. */
  operator: "NEXOLV.TECH",
  operatorType: "Sole proprietorship registered with the Federal Board of Revenue, Pakistan",
  proprietor: "Ibad Ahmed",
  address: {
    line1: "House 1037, Street 21",
    line2: "Phase 5, Bahria Town",
    city: "Rawalpindi",
    region: "Punjab",
    country: "Pakistan",
  },
  email: "nexolv.tech@gmail.com",
  phone: "+92 332 3285685",
  phoneHref: "tel:+923323285685",
  hours: "Monday to Saturday, 10:00–18:00 PKT",
  siteUrl: "https://skilrize.com",
  /** Kept in step with LEGAL_*_VERSION in api/config/settings.py. */
  legalVersion: "2026-09-25",
  legalEffective: "25 September 2026",
  currency: "Pakistani rupees (PKR)",
  /** Default platform commission, mirrored from PLATFORM_COMMISSION_PERCENT. */
  commissionPercent: 10,
  /** Review windows, mirrored from Order.ACCEPTANCE_WINDOW_DAYS and
   *  Contract.REVIEW_WINDOW_DAYS. */
  orderReviewDays: 3,
  contractReviewDays: 7,
} as const;

export function formatAddress(separator = ", "): string {
  const a = BUSINESS.address;
  return [a.line1, a.line2, a.city, a.region, a.country].join(separator);
}

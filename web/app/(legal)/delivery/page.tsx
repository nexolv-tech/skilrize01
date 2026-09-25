import type { Metadata } from "next";
import Link from "next/link";

import { LegalDocument, OperatorBlock } from "@/components/legal";
import { BUSINESS } from "@/lib/business";

export const metadata: Metadata = {
  title: "Service Delivery Policy",
  description: "What SkilRize sells, how an order goes from checkout to delivery, and how long each step takes.",
};

const SECTIONS: Array<[string, string]> = [
  ["what", "What we sell"],
  ["order-flow", "From checkout to delivery"],
  ["timing", "Delivery times"],
  ["how", "How work is delivered"],
  ["briefs", "Briefs and contracts"],
  ["plans", "Plans"],
  ["where", "Where we operate"],
  ["support", "Support"],
];

export default function DeliveryPolicyPage() {
  return (
    <LegalDocument
      title="Service Delivery Policy"
      sections={SECTIONS}
      summary={
        <p>
          Everything bought on SkilRize is a digital service, delivered online through your order
          page — nothing is shipped. Each service shows its price, delivery time and revisions
          before you pay. The delivery time starts when you send the freelancer your requirements,
          and your payment stays in escrow until you accept the work.
        </p>
      }
    >
      <h2 id="what">1. What we sell</h2>
      <p>
        SkilRize is an online marketplace operated by {BUSINESS.operator}. Buyers pay for
        professional services performed by independent freelancers — websites and apps, design,
        writing and translation, video, marketing, tutoring and similar work. Every service is
        performed and delivered electronically. We do not sell or ship physical goods.
      </p>
      <p>
        We also sell optional <Link href="/pricing">Pro and Elite plans</Link>, which give
        freelancers more proposals each month, team seats, analytics and other tools.
      </p>

      <h2 id="order-flow">2. From checkout to delivery</h2>
      <ol>
        <li>
          <strong>Choose a service.</strong> Browse <Link href="/gigs">services</Link> or search.
          Each listing shows up to three packages with a fixed price, delivery time, number of
          revisions and what is included, plus optional extras.
        </li>
        <li>
          <strong>Check out.</strong> Pick a package and click <em>Continue to checkout</em>. The
          checkout page shows the total, the delivery time and the freelancer. To place the order
          you sign in, or create an account and verify your email and identity card.
        </li>
        <li>
          <strong>Pay.</strong> Transfer the total to {BUSINESS.operator}&apos;s business bank
          account shown at checkout, enter the transfer reference, and confirm. The money is held
          in escrow — the freelancer cannot touch it yet. You get an order page straight away.
        </li>
        <li>
          <strong>Send your requirements.</strong> Answer the freelancer&apos;s questions and attach
          any files they need. The delivery clock starts now.
        </li>
        <li>
          <strong>The work is done.</strong> You and the freelancer talk and share files in the
          order&apos;s messages. You can follow progress on the order page.
        </li>
        <li>
          <strong>Delivery.</strong> The freelancer delivers through the order page. We notify you
          by email and in the app.
        </li>
        <li>
          <strong>Review.</strong> Accept the delivery, or request a revision if your package
          includes one. If you do not respond within {BUSINESS.orderReviewDays} days, the delivery
          is accepted automatically.
        </li>
        <li>
          <strong>Payment released.</strong> The payment goes to the freelancer, minus the{" "}
          {BUSINESS.commissionPercent}% platform fee. The order is complete, and you can review
          each other.
        </li>
      </ol>
      <p>
        If the order is cancelled before delivery, you are refunded in full — see the{" "}
        <Link href="/refunds">Refund &amp; Cancellation Policy</Link>.
      </p>

      <h2 id="timing">3. Delivery times</h2>
      <ul>
        <li>
          Each package states its delivery time in days. Extras you add may extend it; the checkout
          page shows the total before you pay.
        </li>
        <li>
          The time is counted in calendar days from the moment you send your requirements, not from
          payment — a freelancer cannot start work they have not been briefed on.
        </li>
        <li>
          Your order page shows the due date. If it passes without a delivery, you may cancel for a
          full refund.
        </li>
        <li>
          A revision request gives the freelancer time to rework the delivery; the order returns to
          you once they re-deliver.
        </li>
      </ul>

      <h2 id="how">4. How work is delivered</h2>
      <ul>
        <li>
          Deliveries are uploaded to the order page: documents, design files, source code, video,
          or a link to where the work is hosted. Every uploaded file is scanned for viruses.
        </li>
        <li>
          You download delivered files from the order page through secure links that are created
          when you ask for them and expire after a few minutes. The files stay in your order.
        </li>
        <li>
          Work that has to be installed or published — a website going live, for example — is
          agreed between you and the freelancer in the order&apos;s messages.
        </li>
      </ul>

      <h2 id="briefs">5. Briefs and contracts</h2>
      <p>
        If you post a brief instead of buying a listed service, freelancers send proposals with
        their price and timeline. When you award one, the contract states its milestones. You fund
        each milestone before its work starts; the freelancer submits it on the contract page; and
        you approve it within {BUSINESS.contractReviewDays} days, after which it is approved
        automatically and the payment released.
      </p>

      <h2 id="plans">6. Plans</h2>
      <p>
        A Pro or Elite plan is active as soon as you confirm payment, for the 30 days or 12 months
        you chose. Its benefits apply to your account immediately. Plans do not renew
        automatically.
      </p>

      <h2 id="where">7. Where we operate</h2>
      <p>
        SkilRize is run from Pakistan and priced in {BUSINESS.currency}. Anyone aged 18 or over may
        use it, wherever they live, but payments are currently made by bank transfer to a Pakistani
        bank account.
      </p>

      <h2 id="support">8. Support</h2>
      <p>
        We answer email within one business day, {BUSINESS.hours}. Include your order number so we
        can find it quickly.
      </p>
      <OperatorBlock />
    </LegalDocument>
  );
}

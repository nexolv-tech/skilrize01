import type { Metadata } from "next";
import Link from "next/link";

import { LegalDocument, OperatorBlock } from "@/components/legal";
import { BUSINESS } from "@/lib/business";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The agreement between you and SkilRize: accounts, fees, escrow payments, orders, contracts and conduct.",
};

const SECTIONS: Array<[string, string]> = [
  ["agreement", "This agreement"],
  ["eligibility", "Who can use SkilRize"],
  ["account", "Your account"],
  ["how", "How SkilRize works"],
  ["fees", "Fees"],
  ["escrow", "Payments and escrow"],
  ["services", "Buying a service"],
  ["projects", "Briefs and contracts"],
  ["cancellations", "Cancellations and refunds"],
  ["reviews", "Reviews"],
  ["conduct", "What is not allowed"],
  ["ip", "Content and ownership"],
  ["disputes", "When something goes wrong"],
  ["suspension", "Suspension and closure"],
  ["liability", "Our responsibility"],
  ["law", "Governing law"],
  ["changes", "Changes"],
  ["contact", "Contact"],
];

export default function TermsPage() {
  return (
    <LegalDocument
      title="Terms of Service"
      sections={SECTIONS}
      summary={
        <p>
          SkilRize connects people who need work done with freelancers who do it. When you order,
          your payment is held in escrow and released to the freelancer only when you approve the
          work — or automatically if you do not respond in time — and refunded if the order is
          cancelled. Buyers pay the listed price; freelancers pay a {BUSINESS.commissionPercent}%
          platform fee from what they earn. Keep payments on SkilRize, verify your identity, and
          treat people honestly.
        </p>
      }
    >
      <h2 id="agreement">1. This agreement</h2>
      <p>
        These Terms are a contract between you and {BUSINESS.operator}, which operates SkilRize.
        You accept them when you create an account. Our{" "}
        <Link href="/privacy">Privacy Policy</Link>,{" "}
        <Link href="/refunds">Refund &amp; Cancellation Policy</Link> and{" "}
        <Link href="/delivery">Service Delivery Policy</Link> form part of them.
      </p>

      <h2 id="eligibility">2. Who can use SkilRize</h2>
      <ul>
        <li>You must be at least 18 years old and able to enter a binding contract.</li>
        <li>You may hold one personal account. A business may operate through one account per person who uses it.</li>
        <li>The information you give us must be true, and you must keep it up to date.</li>
      </ul>

      <h2 id="account">3. Your account</h2>
      <p>
        You are responsible for everything done through your account, so keep your password to
        yourself and turn on two-factor authentication. Before you can buy, sell, publish a service
        or send a proposal, you must verify your email address and your national identity card
        (CNIC); we may also ask you to verify your phone number. Verification protects everyone
        you deal with — it is not optional for anyone who moves money.
      </p>

      <h2 id="how">4. How SkilRize works</h2>
      <p>There are two ways to work, on the same account:</p>
      <ul>
        <li>
          <strong>Services:</strong> a freelancer lists a service in up to three packages, each
          with a fixed price, delivery time and number of revisions. You buy a package outright.
        </li>
        <li>
          <strong>Briefs:</strong> you describe the work, freelancers send proposals, and you
          award a contract — paid as one amount, in milestones, or by the hour.
        </li>
      </ul>
      <p>
        Freelancers are independent. They are not our employees or agents, and the contract for
        the work is between the buyer and the freelancer. Our role is to run the marketplace and
        to hold payments in escrow until they are released or refunded under these Terms.
      </p>
      <p>
        Verified university students can also use a <strong>campus portal</strong>: the same
        marketplace, visible only to verified students of their university.
      </p>

      <h2 id="fees">5. Fees</h2>
      <ul>
        <li>
          <strong>Buyers</strong> pay the listed price. There is no additional service fee.
        </li>
        <li>
          <strong>Freelancers</strong> pay a platform fee of {BUSINESS.commissionPercent}% of each
          payment, deducted when the payment is released. The amount you will receive is shown
          before any payment is released.
        </li>
        <li>
          <strong>Paid plans</strong> (Pro and Elite) are optional and priced on the{" "}
          <Link href="/pricing">Pricing page</Link>. They run for the period you pay for and do not
          renew automatically.
        </li>
      </ul>
      <p>
        We may change fees with at least 30 days&apos; notice. A change never applies to an order
        or contract that is already funded.
      </p>

      <h2 id="escrow">6. Payments and escrow</h2>
      <ul>
        <li>
          All prices are in {BUSINESS.currency}. Today you pay by bank transfer to{" "}
          {BUSINESS.operator}&apos;s business account, whose details are shown at checkout; card
          and mobile-wallet payments are being added.
        </li>
        <li>
          When you confirm that you have paid, the order starts on your word. If the payment does
          not reach our account within three business days, we may cancel the order. Confirming a
          payment you have not made is fraud, and we will close the account that does it.
        </li>
        <li>
          Money you pay is held by us in escrow. Neither side can use it while it is held.
        </li>
        <li>
          It is <strong>released</strong> to the freelancer when the buyer accepts the delivery,
          or automatically if the buyer does not respond within the review window —{" "}
          {BUSINESS.orderReviewDays} days for a service order, {BUSINESS.contractReviewDays} days
          for a contract milestone.
        </li>
        <li>
          It is <strong>refunded</strong> to the buyer when an order or milestone is cancelled
          under section 9.
        </li>
        <li>
          We aim to send payouts within seven business days of a release, to the bank account on
          the freelancer&apos;s verified payout profile. A freelancer must complete that profile to
          be paid.
        </li>
      </ul>

      <h2 id="services">7. Buying a service</h2>
      <ol>
        <li>You choose a package and any extras, and pay. The payment is held in escrow.</li>
        <li>You answer the freelancer&apos;s requirements. The delivery time starts only then.</li>
        <li>The freelancer delivers through SkilRize.</li>
        <li>
          You accept the delivery, or request a revision if your package includes one. Once the
          review window passes without a response, the delivery is accepted automatically.
        </li>
      </ol>
      <p>
        What a package includes is fixed when you buy it; a freelancer editing the listing later
        does not change your order. See the <Link href="/delivery">Service Delivery Policy</Link>.
      </p>

      <h2 id="projects">8. Briefs and contracts</h2>
      <p>
        The terms of a contract — price, milestones, hours — are fixed when the freelancer accepts
        it. Each milestone is funded before the work on it starts, and released when the client
        approves it. On an hourly contract, the client sets a weekly hour limit; the freelancer is
        not paid for hours over it. A client may offer a short paid trial before awarding the
        whole brief; a trial is a contract of its own.
      </p>

      <h2 id="cancellations">9. Cancellations and refunds</h2>
      <p>
        Every cancellation that returns money refunds the buyer in full. Who can cancel, and when,
        is set out in the <Link href="/refunds">Refund &amp; Cancellation Policy</Link>. In short:
        a freelancer can cancel undelivered work at any time; a buyer can cancel before sending
        requirements, or once an order is past its due date; delivered work cannot be cancelled,
        and a released payment is final.
      </p>

      <h2 id="reviews">10. Reviews</h2>
      <p>
        When a contract ends, both sides may review each other. Neither review is shown until both
        are submitted or the review period ends, so nobody reviews in reply to the other. Reviews
        must be honest and about the work. We check for manipulation — reviews exchanged between
        linked accounts, for example — and may exclude such reviews from ratings.
      </p>

      <h2 id="conduct">11. What is not allowed</h2>
      <ul>
        <li>
          Taking payment outside SkilRize for work found here. It removes the protection escrow
          gives both of you, and we may close accounts that do it.
        </li>
        <li>Anything illegal in Pakistan, and any service that helps someone break the law.</li>
        <li>
          Academic dishonesty: completing graded coursework, exams or theses for someone to submit
          as their own. Tutoring, research help and editing are welcome.
        </li>
        <li>Copying other people&apos;s work, or infringing copyright or trademarks.</li>
        <li>Harassment, hate, threats, or sharing someone&apos;s personal information without consent.</li>
        <li>Fake accounts, fake reviews, spam, and misleading listings.</li>
        <li>Attempting to break, overload or probe the platform&apos;s security.</li>
      </ul>

      <h2 id="ip">12. Content and ownership</h2>
      <p>
        You own what you post. You allow us to display it on SkilRize so the marketplace can work.
        Unless a buyer and freelancer agree otherwise in writing, ownership of the delivered work
        passes to the buyer once its payment is released. The freelancer may show the work in their
        portfolio only if the buyer agrees.
      </p>

      <h2 id="disputes">13. When something goes wrong</h2>
      <p>
        Talk to each other first — most problems are solved by a message. If that does not work,
        contact us before accepting a delivery or before a review window ends. We will look at the
        order record, messages and files, and decide in good faith how the held payment should be
        released or refunded. Our decision on held funds is final for the platform, without
        affecting your rights under Pakistani law.
      </p>

      <h2 id="suspension">14. Suspension and closure</h2>
      <p>
        We may suspend or close an account that breaks these Terms, puts others at risk, or that
        the law requires us to act on. Money already held in escrow is then released or refunded
        under these Terms. You may close your account at any time from{" "}
        <Link href="/settings/privacy">Settings → Privacy &amp; data</Link>, once no money is still
        moving.
      </p>

      <h2 id="liability">15. Our responsibility</h2>
      <p>
        We work hard to keep SkilRize available and secure, but we cannot promise it will never be
        interrupted. We are not responsible for the quality of work freelancers deliver, beyond the
        escrow and refund protections in these Terms. To the extent the law allows, our total
        liability to you is limited to the fees you paid us in the twelve months before the claim.
        Nothing here limits liability that cannot be limited by law.
      </p>

      <h2 id="law">16. Governing law</h2>
      <p>
        These Terms are governed by the laws of Pakistan. The courts at {BUSINESS.address.city}{" "}
        have jurisdiction over any dispute that we cannot resolve together.
      </p>

      <h2 id="changes">17. Changes</h2>
      <p>
        We will tell you by email or in the app at least 30 days before a change that affects you
        takes effect. If you do not agree, you may close your account before then.
      </p>

      <h2 id="contact">18. Contact</h2>
      <OperatorBlock />
    </LegalDocument>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import { LegalDocument, OperatorBlock } from "@/components/legal";
import { BUSINESS } from "@/lib/business";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy",
  description: "When an order or contract can be cancelled on SkilRize, who can cancel it, and how refunds are paid.",
};

const SECTIONS: Array<[string, string]> = [
  ["principle", "How refunds work"],
  ["orders", "Service orders"],
  ["contracts", "Contracts and milestones"],
  ["delivered", "After delivery"],
  ["plans", "Plans and promotions"],
  ["how-paid", "How you receive a refund"],
  ["fraud", "Payments that never arrive"],
  ["contact", "Contact"],
];

export default function RefundPolicyPage() {
  return (
    <LegalDocument
      title="Refund & Cancellation Policy"
      sections={SECTIONS}
      summary={
        <p>
          Your money sits in escrow until you approve the work. If an order is cancelled before
          delivery, you get all of it back — no fee is deducted. You can cancel before you send
          requirements, or once the freelancer misses the due date; the freelancer can cancel any
          time before delivering. We pay refunds to the account you paid from, within seven
          business days.
        </p>
      }
    >
      <h2 id="principle">1. How refunds work</h2>
      <p>
        On SkilRize a payment is never sent straight to the freelancer. It is held in escrow by{" "}
        {BUSINESS.operator} and only released when the buyer accepts the work (or the review
        window passes). Until then, it can be returned. That is what makes a refund possible —
        and why a <strong>released payment is final</strong>.
      </p>
      <p>
        When a refund is due, it is <strong>the full amount you paid</strong> for that order or
        milestone. We do not keep a fee on cancelled work.
      </p>

      <h2 id="orders">2. Service orders</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Situation</th>
            <th scope="col">Who can cancel</th>
            <th scope="col">Refund</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>You have paid but not yet sent the requirements</td>
            <td>Buyer or freelancer</td>
            <td>Full</td>
          </tr>
          <tr>
            <td>The freelancer is working and the order is not yet due</td>
            <td>Freelancer (the buyer can ask them to)</td>
            <td>Full</td>
          </tr>
          <tr>
            <td>The order is past its due date and nothing has been delivered</td>
            <td>Buyer or freelancer</td>
            <td>Full</td>
          </tr>
          <tr>
            <td>The work has been delivered</td>
            <td>No one — see section 4</td>
            <td>—</td>
          </tr>
          <tr>
            <td>You accepted the delivery, or the {BUSINESS.orderReviewDays}-day review window passed</td>
            <td>No one — the payment was released</td>
            <td>None</td>
          </tr>
        </tbody>
      </table>
      <p>
        Each order page shows whether you can cancel it right now, and if not, why not. The due
        date is counted from when you send the requirements.
      </p>

      <h2 id="contracts">3. Contracts and milestones</h2>
      <ul>
        <li>
          <strong>Before any money is funded</strong>, either side can cancel a contract; there is
          nothing to refund.
        </li>
        <li>
          <strong>The freelancer</strong> can cancel a funded contract as long as no milestone is
          waiting for the client&apos;s review. Every funded milestone that has not been released is
          refunded to the client in full.
        </li>
        <li>
          <strong>The client</strong> cannot cancel while money is held — so that a freelancer is
          never left unpaid for work already started. Ask the freelancer to cancel, or contact us
          and we will review it.
        </li>
        <li>
          <strong>Milestones already released</strong> are final and are not refunded.
        </li>
        <li>
          <strong>Hourly contracts</strong> are billed for hours logged within the weekly limit you
          set. Tell us within the review period if logged hours are wrong.
        </li>
      </ul>

      <h2 id="delivered">4. After delivery</h2>
      <p>
        Once work is delivered, you decide what happens next:
      </p>
      <ul>
        <li><strong>Accept it</strong> — the payment is released to the freelancer.</li>
        <li>
          <strong>Request a revision</strong>, if your package includes one — explain what does
          not match what you ordered.
        </li>
        <li>
          <strong>Contact us</strong> if the delivery is not what was agreed and the freelancer will
          not put it right. Do this before the review window ends — {BUSINESS.orderReviewDays} days
          for a service order, {BUSINESS.contractReviewDays} days for a milestone. We will review
          the order and may refund you in full or in part.
        </li>
      </ul>
      <p>
        If you do nothing, the delivery is accepted automatically when the review window ends, and
        the payment is released.
      </p>

      <h2 id="plans">5. Plans and promotions</h2>
      <ul>
        <li>
          <strong>Pro and Elite plans</strong> never renew on their own. Cancelling stops the plan
          at the end of the period you paid for; we do not refund part of a period, except where
          we charged you in error.
        </li>
        <li>
          <strong>Promoted listings</strong>: the budget you set is a limit, not a payment. You are
          only ever charged for what a promotion has spent, and pausing it stops the spending
          immediately. Budget already spent is not refundable.
        </li>
      </ul>

      <h2 id="how-paid">6. How you receive a refund</h2>
      <ul>
        <li>
          Refunds are paid to the account you paid from, within seven business days of the
          cancellation. Your order page shows the refund&apos;s status, and we email you when it
          is sent.
        </li>
        <li>
          We cover the transfer cost. Your own bank may charge a fee to receive money; we cannot
          control that.
        </li>
        <li>
          If we cannot send the refund to the original account, we will contact you to confirm a
          different account in your name.
        </li>
      </ul>

      <h2 id="fraud">7. Payments that never arrive</h2>
      <p>
        An order starts when the buyer confirms they have paid. If the payment does not reach our
        account within three business days, we cancel the order and nothing is owed to either side.
        Confirming a payment you did not make is fraud; we close the account and may report it.
        See the <Link href="/terms">Terms of Service</Link>, section 6.
      </p>

      <h2 id="contact">8. Contact</h2>
      <p>
        For a refund question, email <a href={`mailto:${BUSINESS.email}`}>{BUSINESS.email}</a> with
        your order number, or call us during {BUSINESS.hours}.
      </p>
      <OperatorBlock />
    </LegalDocument>
  );
}

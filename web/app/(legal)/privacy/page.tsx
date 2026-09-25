import type { Metadata } from "next";
import Link from "next/link";

import { LegalDocument, OperatorBlock } from "@/components/legal";
import { BUSINESS } from "@/lib/business";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What personal data SkilRize collects, why, who sees it, how long it is kept, and your rights over it.",
};

const SECTIONS: Array<[string, string]> = [
  ["who-we-are", "Who we are"],
  ["what-we-collect", "What we collect"],
  ["why", "Why we use it"],
  ["automated", "Automated decisions"],
  ["sharing", "Who we share it with"],
  ["transfers", "Where it is stored"],
  ["retention", "How long we keep it"],
  ["rights", "Your rights"],
  ["security", "How we protect it"],
  ["children", "Age limit"],
  ["cookies", "Cookies"],
  ["changes", "Changes to this policy"],
  ["contact", "Contact"],
];

export default function PrivacyPolicyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      sections={SECTIONS}
      summary={
        <p>
          We collect what we need to run a marketplace that holds money safely: your account
          details, identity verification, and the record of what you buy and sell. We do not sell
          your data, show you ads, or use tracking cookies. Your identity-card and bank details are
          encrypted. You can download everything we hold about you, or delete your account, from{" "}
          <Link href="/settings/privacy" className="font-medium text-accent underline underline-offset-2">
            Settings → Privacy &amp; data
          </Link>
          . We follow the EU General Data Protection Regulation (GDPR) for every user, wherever
          they live.
        </p>
      }
    >
      <h2 id="who-we-are">1. Who we are</h2>
      <p>
        SkilRize ({BUSINESS.siteUrl.replace("https://", "")}) is operated by the business below,
        which is the <strong>controller</strong> of your personal data — the party responsible for
        deciding how it is used.
      </p>
      <OperatorBlock />
      <p>
        For anything about your personal data, write to{" "}
        <a href={`mailto:${BUSINESS.email}`}>{BUSINESS.email}</a> with “Privacy” in the subject.
      </p>

      <h2 id="what-we-collect">2. What we collect</h2>
      <h3>Information you give us</h3>
      <ul>
        <li>
          <strong>Account details:</strong> your name, email address and password. Passwords are
          stored only as a one-way hash (Argon2id) — nobody, including us, can read them.
        </li>
        <li>
          <strong>Verification:</strong> your phone number, a photo of your national identity card
          (CNIC), and — if you verify as a student — your university email address and a photo of
          your student ID card.
        </li>
        <li>
          <strong>Payout details</strong> (freelancers only): bank name, account title, account
          number, CNIC number and mobile-wallet number, so we can send you what you earn.
        </li>
        <li>
          <strong>Profile:</strong> photo, headline, bio, skills, languages, city and country, and
          the portfolio images you upload.
        </li>
        <li>
          <strong>Marketplace activity:</strong> the services you list, briefs you post, proposals,
          orders, contracts, files you deliver, time you log, messages, reviews and community posts.
        </li>
        <li>
          <strong>Payments:</strong> the amount, date and the transfer reference you give when you
          pay for an order. We do not currently accept cards, so we never receive card numbers.
        </li>
        <li>
          <strong>Messages to us</strong>, if you contact support.
        </li>
      </ul>
      <h3>Information collected automatically</h3>
      <ul>
        <li>
          <strong>Security data:</strong> your IP address, browser and device type, and when you
          sign in. We keep a keyed fingerprint of each device you use so we can alert you to, and
          briefly hold payments from, a device you have not used before.
        </li>
        <li>
          <strong>Search terms</strong> typed into our search, stored without any link to who
          searched.
        </li>
        <li>
          <strong>Cookies</strong> needed to keep you signed in — see the{" "}
          <Link href="/cookies">Cookie Policy</Link>. We use no analytics or advertising cookies.
        </li>
      </ul>
      <h3>Information from services you connect</h3>
      <p>
        If you choose to connect Zoom, Google Meet, GitHub, Figma or Notion to a contract, we store
        an encrypted access token and the limited activity that service shares (for example,
        commits to a repository you linked). You can disconnect at any time from Settings →
        Integrations. With the mobile app, we store a notification token for your device if you
        allow notifications.
      </p>

      <h2 id="why">3. Why we use it, and on what legal basis</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Purpose</th>
            <th scope="col">Legal basis (GDPR Art. 6)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Creating your account, running orders and contracts, holding and releasing payments, paying freelancers, messaging</td>
            <td>Performing our contract with you</td>
          </tr>
          <tr>
            <td>Verifying identity (email, phone, CNIC) before anyone moves money</td>
            <td>Legitimate interest in preventing fraud, and our contract with you</td>
          </tr>
          <tr>
            <td>Keeping financial and transaction records</td>
            <td>Legal obligation (tax and accounting law)</td>
          </tr>
          <tr>
            <td>Security: sign-in protection, new-device checks, rate limits, virus-scanning uploads, audit logs</td>
            <td>Legitimate interest in keeping accounts and money safe</td>
          </tr>
          <tr>
            <td>Search ranking, seller levels and review-integrity checks</td>
            <td>Legitimate interest in a fair, trustworthy marketplace</td>
          </tr>
          <tr>
            <td>Connecting optional integrations, mobile push notifications</td>
            <td>Your consent, which you can withdraw at any time</td>
          </tr>
          <tr>
            <td>Service emails (order updates, security alerts)</td>
            <td>Performing our contract; announcement emails can be turned off in Settings → Notifications</td>
          </tr>
        </tbody>
      </table>
      <p>We do not use your data for advertising and we do not sell it to anyone.</p>

      <h2 id="automated">4. Automated decisions</h2>
      <p>Some decisions on SkilRize are made by software. None of them has legal effect on you without a person being able to review it:</p>
      <ul>
        <li>
          <strong>Search ranking</strong> combines how well a listing matches your search, the
          seller&apos;s reputation, how recent the listing is, and paid promotion. Promoted
          listings are always labelled.
        </li>
        <li>
          <strong>Job Success Score and seller levels</strong> are calculated from completed
          contracts, ratings, on-time delivery and repeat clients.
        </li>
        <li>
          <strong>Review integrity checks</strong> look for signs of manipulated reviews (for
          example, two accounts reviewing each other repeatedly). A review with enough signals is
          hidden from scoring — never deleted.
        </li>
      </ul>
      <p>
        If you think one of these has treated you unfairly, contact us and a person will review it.
      </p>

      <h2 id="sharing">5. Who we share it with</h2>
      <ul>
        <li>
          <strong>Other users</strong> see your public profile, listings and reviews, and the
          people you work with see what an order or contract needs (your name, messages and
          delivered work). Your identity card, bank details and phone number are never shown to
          other users.
        </li>
        <li>
          <strong>Service providers</strong> who process data on our behalf, under contract:
          Oracle Cloud Infrastructure (hosting), Google (email delivery), and Backblaze (off-site
          backup storage).
        </li>
        <li>
          <strong>Banks and payment providers</strong>, to receive payments and send payouts and
          refunds. When card and mobile-wallet payments launch, a licensed Pakistani payment
          service provider will process them, and this policy will name it.
        </li>
        <li>
          <strong>Services you connect</strong> yourself (see section 2).
        </li>
        <li>
          <strong>Authorities</strong>, when Pakistani law requires it, or to protect someone from
          fraud or harm.
        </li>
        <li>
          <strong>A buyer of the business</strong>, if SkilRize is ever sold or merged — under this
          same policy.
        </li>
      </ul>

      <h2 id="transfers">6. Where it is stored</h2>
      <p>
        Our servers run on Oracle Cloud in its Mumbai, India region. Email passes through Google,
        which may process it in other countries. Where your data leaves Pakistan or the European
        Economic Area, we rely on our providers&apos; contractual data-protection commitments
        (including the EU Standard Contractual Clauses where they apply).
      </p>

      <h2 id="retention">7. How long we keep it</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Data</th>
            <th scope="col">Kept for</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Your account and profile</td>
            <td>Until you delete your account</td>
          </tr>
          <tr>
            <td>Identity-card and student-ID images, payout details, devices, sessions, notifications</td>
            <td>Deleted when you delete your account</td>
          </tr>
          <tr>
            <td>Orders, contracts, payments, payouts and refunds</td>
            <td>Six years, as Pakistani tax law requires — attributed to “Deleted user” once your account is deleted</td>
          </tr>
          <tr>
            <td>Reviews, messages and community posts</td>
            <td>Kept as part of other people&apos;s history, attributed to “Deleted user”</td>
          </tr>
          <tr>
            <td>Security audit log</td>
            <td>As long as needed to investigate fraud and abuse</td>
          </tr>
          <tr>
            <td>Sign-in codes and password-reset links</td>
            <td>Minutes; they expire automatically</td>
          </tr>
        </tbody>
      </table>

      <h2 id="rights">8. Your rights</h2>
      <p>Wherever you live, you can:</p>
      <ul>
        <li>
          <strong>Get a copy</strong> of your data (access and portability) — download it
          instantly as a JSON file from{" "}
          <Link href="/settings/privacy">Settings → Privacy &amp; data</Link>.
        </li>
        <li>
          <strong>Correct it</strong> — edit your profile in Settings, or ask us.
        </li>
        <li>
          <strong>Delete it</strong> — delete your account from the same page. Some records are
          kept for the reasons in section 7, and the page tells you what before you confirm.
        </li>
        <li>
          <strong>Object or restrict</strong> — ask us to stop or limit a use based on legitimate
          interest.
        </li>
        <li>
          <strong>Withdraw consent</strong> — disconnect an integration or turn off notifications
          at any time.
        </li>
        <li>
          <strong>Complain</strong> to a data-protection authority. If you are in the EU, that is
          your country&apos;s supervisory authority. We would appreciate the chance to put it right
          first.
        </li>
      </ul>
      <p>
        We answer requests sent by email within one month, and may ask you to confirm your
        identity first so we never hand your data to someone else.
      </p>

      <h2 id="security">9. How we protect it</h2>
      <ul>
        <li>All traffic is encrypted with HTTPS, and browsers are told never to connect without it.</li>
        <li>Identity-card numbers, bank account numbers, two-factor secrets and connected-service tokens are encrypted in our database (AES-256-GCM).</li>
        <li>Uploaded files are checked, re-encoded to strip hidden data, scanned for viruses, and only ever served through links that expire within minutes.</li>
        <li>Two-factor authentication is available to everyone and required before money moves.</li>
        <li>Staff access is limited by role, requires two-factor authentication, and every sensitive action is written to an audit log that cannot be edited.</li>
      </ul>
      <p>
        If a breach ever puts your data at risk, we will tell you and — where the law requires —
        the relevant authority, without undue delay (within 72 hours for authorities under the
        GDPR).
      </p>

      <h2 id="children">10. Age limit</h2>
      <p>
        SkilRize is for people aged 18 and over. We do not knowingly collect data from anyone
        younger; if we learn we have, we delete it.
      </p>

      <h2 id="cookies">11. Cookies</h2>
      <p>
        We use only the cookies needed to keep you signed in and protect your forms. The full list
        is in our <Link href="/cookies">Cookie Policy</Link>.
      </p>

      <h2 id="changes">12. Changes to this policy</h2>
      <p>
        Every version of this policy is dated. If we change it in a way that matters, we will tell
        you by email or in the app before the change takes effect.
      </p>

      <h2 id="contact">13. Contact</h2>
      <OperatorBlock />
    </LegalDocument>
  );
}

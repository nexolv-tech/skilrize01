import type { Metadata } from "next";
import Link from "next/link";

import { LegalDocument, OperatorBlock } from "@/components/legal";

export const metadata: Metadata = {
  title: "Cookie Policy",
  description: "The cookies and browser storage SkilRize uses — all of them needed to run the site, none for tracking.",
};

const SECTIONS: Array<[string, string]> = [
  ["summary", "What we use"],
  ["cookies", "Cookies"],
  ["storage", "Browser storage"],
  ["not-used", "What we do not use"],
  ["control", "Your choices"],
  ["contact", "Contact"],
];

const COOKIES: Array<[string, string, string]> = [
  ["skilrize_access", "Proves you are signed in. It cannot be read by scripts on the page.", "15 minutes"],
  ["skilrize_refresh", "Keeps you signed in between visits by renewing the cookie above. It cannot be read by scripts on the page.", "30 days, or until you sign out"],
  ["csrftoken", "Protects your forms from being submitted by another website pretending to be you.", "1 year"],
  ["skilrize_device", "Recognises this browser as one you have signed in from before, so a sign-in from a new device can be checked and a browser update is not mistaken for one. A random value; it cannot be read by scripts on the page.", "400 days, renewed each time you sign in"],
];

const STORAGE: Array<[string, string]> = [
  ["skilrize-theme", "Whether you chose the light or dark theme."],
  ["skilrize.surface", "For verified students, whether you were last on the global marketplace or your campus portal."],
  ["skilrize.cookie-notice", "That you have seen the cookie notice, so it is not shown again."],
];

export default function CookiePolicyPage() {
  return (
    <LegalDocument
      title="Cookie Policy"
      sections={SECTIONS}
      summary={
        <p>
          SkilRize uses three cookies, and all three exist to keep you signed in and your account
          safe. We use no analytics, advertising or social-media cookies, and nothing that follows
          you to other websites. Because every cookie is strictly necessary, the law does not
          require us to ask before setting them — but we want you to know exactly what they are.
        </p>
      }
    >
      <h2 id="summary">1. What we use</h2>
      <p>
        A cookie is a small file a website stores in your browser. We use cookies only for signing
        in and for security. We also keep three preferences in your browser&apos;s local storage,
        which never leave your device.
      </p>

      <h2 id="cookies">2. Cookies</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">What it does</th>
            <th scope="col">How long</th>
          </tr>
        </thead>
        <tbody>
          {COOKIES.map(([name, purpose, duration]) => (
            <tr key={name}>
              <td>
                <code>{name}</code>
              </td>
              <td>{purpose}</td>
              <td>{duration}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        All three are first-party (set by SkilRize itself), sent only over encrypted connections,
        and never shared with anyone else. Our own staff also receive a <code>sessionid</code>{" "}
        cookie when they sign in to the administration site; users never do.
      </p>

      <h2 id="storage">3. Browser storage</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">What it remembers</th>
          </tr>
        </thead>
        <tbody>
          {STORAGE.map(([name, purpose]) => (
            <tr key={name}>
              <td>
                <code>{name}</code>
              </td>
              <td>{purpose}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>These stay in your browser until you clear them. We cannot read them from our servers.</p>

      <h2 id="not-used">4. What we do not use</h2>
      <ul>
        <li>No analytics cookies — we do not use Google Analytics or anything like it.</li>
        <li>No advertising or retargeting cookies.</li>
        <li>No social-media buttons or embedded content that sets cookies of its own.</li>
      </ul>
      <p>
        If that ever changes, we will update this policy first and ask for your consent before
        setting any cookie that is not strictly necessary.
      </p>

      <h2 id="control">5. Your choices</h2>
      <p>
        You can delete or block cookies in your browser settings. If you block the cookies above,
        you will not be able to sign in, but you can still browse services and briefs. Signing out
        removes both sign-in cookies immediately. For how we handle your personal data more
        broadly, see the <Link href="/privacy">Privacy Policy</Link>.
      </p>

      <h2 id="contact">6. Contact</h2>
      <OperatorBlock />
    </LegalDocument>
  );
}

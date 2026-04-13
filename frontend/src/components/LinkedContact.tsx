/**
 * Reusable components for rendering phone numbers and emails as clickable links.
 */

export function PhoneLink({ number }: { number: string }) {
  return (
    <a href={`tel:${number}`} className="hover:underline">
      {number}
    </a>
  );
}

export function EmailLink({ email }: { email: string }) {
  return (
    <a href={`mailto:${email}`} className="hover:underline">
      {email}
    </a>
  );
}

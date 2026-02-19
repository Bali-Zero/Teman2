/**
 * AuthorJsonLd Component
 *
 * Generates Person schema markup for article authors.
 * Include sameAs links to social profiles for entity recognition.
 *
 * Usage:
 * <AuthorJsonLd
 *   name="John Doe"
 *   description="Immigration expert with 10+ years experience"
 *   image="https://balizero.com/authors/john.jpg"
 *   jobTitle="Senior Consultant"
 *   sameAs={[
 *     "https://linkedin.com/in/johndoe",
 *     "https://twitter.com/johndoe",
 *   ]}
 * />
 */

import React from "react";

interface AuthorJsonLdProps {
  name: string;
  description?: string;
  image?: string;
  jobTitle?: string;
  worksFor?: string;
  sameAs?: string[];
  url?: string;
}

export function AuthorJsonLd({
  name,
  description,
  image,
  jobTitle,
  worksFor = "Bali Zero",
  sameAs = [],
  url,
}: AuthorJsonLdProps) {
  const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";
  const authorUrl =
    url || `${baseUrl}/author/${name.toLowerCase().replace(/\s+/g, "-")}`;

  const schema = {
    "@context": "https://schema.org",
    "@type": "Person",
    "@id": `${authorUrl}#person`,
    name,
    url: authorUrl,
    ...(description && { description }),
    ...(image && { image }),
    ...(jobTitle && { jobTitle }),
    ...(sameAs.length > 0 && { sameAs }),
    worksFor: {
      "@type": "Organization",
      name: worksFor,
      url: baseUrl,
    },
  };

  return (
    <script
      id={`author-${name.toLowerCase().replace(/\s+/g, "-")}-jsonld`}
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

/**
 * Pre-configured authors for Bali Zero team
 */
export const BALI_ZERO_AUTHORS = {
  zero: {
    name: "Zero",
    description:
      "Founder & Lead Consultant at Bali Zero. 10+ years expertise in Indonesian immigration and business setup.",
    jobTitle: "Founder & Lead Consultant",
    sameAs: ["https://www.linkedin.com/company/bali-zero"],
  },
  baliZeroTeam: {
    name: "Bali Zero Team",
    description:
      "Expert consultants specializing in Indonesian visa, business setup, and legal compliance.",
    jobTitle: "Expert Consultants",
    sameAs: [
      "https://www.linkedin.com/company/bali-zero",
      "https://www.instagram.com/balizero/",
    ],
  },
};

/**
 * Quick component for using predefined authors
 */
interface PredefinedAuthorProps {
  authorKey: keyof typeof BALI_ZERO_AUTHORS;
}

export function PredefinedAuthorJsonLd({ authorKey }: PredefinedAuthorProps) {
  const author = BALI_ZERO_AUTHORS[authorKey];
  if (!author) return null;
  return <AuthorJsonLd {...author} />;
}

export default AuthorJsonLd;

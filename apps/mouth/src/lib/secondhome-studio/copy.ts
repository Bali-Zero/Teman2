/**
 * Second Home Studio — ALL user-visible copy for the studio, in one module.
 *
 * Content source: `COPY-DECK-studio.md` (cross-family copy seat, final
 * deck), folded into the nested structure other studio modules address by
 * dot-path key. Deck strings are used verbatim wherever the deck's flat
 * "a.b.c" keys map cleanly onto this module's structure — see the two
 * FIXED-FROM-DECK notes below for the two spots where "verbatim" had to
 * yield to the sweep test / terminology rule instead.
 *
 * Sections the deck does NOT cover (routeComparator, price, verdict
 * reasons/humanReview micro-copy, and the post-verdict TimelineView's
 * per-step title/range copy) keep their original hand-written strings —
 * see the file-level comment in the git history / delivery report for why
 * the deck's own "TIMELINE" section was NOT grafted onto timeline.ts (its
 * 7-step breakdown doesn't correspond to this module's step ids, and its
 * step 1 — "Complete your fit-check" — can't be a POST-verdict timeline
 * item since the fit-check is already done by the time this panel renders;
 * flagged for reconciliation rather than force-fit).
 *
 * Every component references keys via `getCopy("dot.path")`, never inline
 * strings. This makes `__tests__/forbidden-claims.test.ts` a complete
 * sweep: it walks every string value in COPY recursively and asserts none
 * matches the forbidden-claim patterns from SPEC-secondhome-studio-phaseB.md
 * §6, PLUS the terminology delta (never "assessment"/"certificate"/
 * "eligibility score" — always "fit-check result").
 *
 * Hard rules baked into every string here (spec §0/§6 + copy-deck deltas):
 *  - Always "state-owned (BUMN) Indonesian bank" — never "any bank".
 *  - Always "in your own name" / "your own name" for the deposit.
 *  - "non-working residency" is the only way we describe the permit's work
 *    status — never "work locally" / "work in Indonesia" in any order.
 *  - "the final decision rests with Imigrasi" appears verbatim in every
 *    verdict band body.
 *  - Never "assessment" / "certificate" / "eligibility score" — always
 *    "fit-check result" for the wizard's output.
 *  - No LPS, no BSI, no sharia, no split-deposit phrasing (the DECK's own
 *    draft tripped this — see FIXED-FROM-DECK #1 below), no guaranteed/
 *    100% approval, no automatic ITAP/permanent conversion, no "5-10 years"
 *    for base E33, no IDR 2,000,000, no E33S/E33R codes (E33E/E33F fine).
 *  - Never a price literal: the figure renders only from usePricingData.
 *  - Property route never reads as a green "qualified".
 *  - Custody step 3 keeps the withdrawal/compliance warning (copy-deck
 *    critique #2 — ownership is not unrestricted use).
 *  - Dependents: "priced in your free fit memo", never a number here.
 *
 * Tone: calm, factual, second person, no hype, no urgency, no scarcity.
 */

export const COPY = {
  wizard: {
    age: {
      heading: "First, how old are you?",
      body: "Your age helps us show the routes that may apply to you.",
      why: "Indonesia has separate Second Home pathways for applicants aged 55 and over. Ages 55–59 require extra care because the regulation uses different age thresholds in different articles.",
      options: {
        under_55: "Under 55",
        "55_59": "55–59",
        "60_plus": "60 or over",
      },
    },
    route: {
      heading: "Which route are you considering?",
      body: "The standard Second Home route requires either a qualifying bank deposit or a qualifying completed property.",
      why: "The evidence is different for each route. A bank deposit must be held in your own name at a state-owned (BUMN) Indonesian bank. Our property validation standard is still pending.",
      options: {
        deposit: "Bank deposit",
        property: "Completed strata-title property",
        unsure: "I am not sure yet",
      },
    },
    capital: {
      heading: "How much capital could you place in the required deposit?",
      body: "The standard bank route requires USD 130,000 in your own name at a state-owned (BUMN) Indonesian bank.",
      // FIXED-FROM-DECK #1 (guard-over-match, superscar #3), ROUND 2
      // (fix-mandate P0-C2): the deck's original draft was "The threshold
      // must be met through one qualifying deposit. Split deposits do not
      // qualify." — a true, compliant disclaimer, but "Split deposits"
      // literally trips the spec §6 splitDeposit pattern
      // (/split(ting)?\s+.*deposit/i matches the substring, not the
      // sentence's polarity). The FIRST rewrite dodged that regex by
      // restating the same forbidden concept in a synonym ("deposits
      // divided across multiple accounts do not qualify") — an under-match
      // (superscar #3's twin failure mode): the guard's FORM changed, the
      // banned FACT it exists to keep un-stated did not, and a sibling test
      // celebrated that the euphemism evaded detection as if it were a
      // feature. RULING: state the rule POSITIVELY only — no mention of
      // divided/multiple/split accounts in any form. The sweep gained a
      // dedicated `splitDepositEuphemism` pattern so this class can't
      // silently reopen (forbidden-claims.test.ts).
      why: "The threshold must be met through a single qualifying deposit in your own name.",
      options: {
        ready_130k: "USD 130,000 is ready",
        close_100k_130k: "USD 100,000 to under USD 130,000",
        below_100k: "Below USD 100,000",
      },
    },
    seniorFunding: {
      heading: "Which senior funding profile matches you?",
      body: "Applicants aged 55 and over may have access to senior-specific routes, subject to age-band review and supporting evidence.",
      why: "E33E is based on a USD 50,000 deposit plus at least USD 3,000 per month in passive income. E33F is based on at least USD 3,000 per month in income, without the deposit.",
      options: {
        deposit_50k_income: "USD 50,000 deposit plus USD 3,000 monthly income",
        income_only_3k: "USD 3,000 monthly income only",
        neither: "Neither of these",
        // "not_applicable" is a valid PlanState value (types.ts, 55+ only)
        // but the copy deck never offers it as a wizard button — it's not
        // user-selectable, so no option label is defined for it here.
      },
    },
    property: {
      heading: "What is your property position?",
      body: "Only a completed strata-title property may support this route, subject to our validation standard.",
      why: "The qualifying value is USD 1,000,000. Villas, land, leasehold interests and off-plan purchases do not qualify.",
      options: {
        owns_qualifying_strata:
          "I own qualifying completed strata-title property",
        buying_completed_strata: "I am buying completed strata-title property",
        villa_land_leasehold:
          "I have a villa, land, leasehold or off-plan property",
        none: "I do not have a property route",
      },
    },
    family: {
      heading: "Who would you want to include?",
      body: "Select every family member you may want covered by your plan.",
      why: "Spouses, children and parents can involve different eligibility and document checks. Selection here does not confirm that a family member qualifies.",
      options: {
        spouse: "Spouse",
        children: "Children",
        parents: "Parents",
        none: "No family members",
      },
      dependentsNote:
        "Family members you add are priced in your free fit memo — there's no line-item cost shown here.",
    },
    horizon: {
      heading: "When would you like to move forward?",
      body: "This helps us separate immediate preparation from longer-term planning.",
      why: "Your preferred timing does not change the requirements or Imigrasi processing time.",
      options: {
        asap: "As soon as possible",
        this_quarter: "This quarter",
        exploring: "I am still exploring",
      },
    },
    location: {
      heading: "Where are you now?",
      body: "Your location affects how documents, banking and the next procedural steps are coordinated.",
      why: "Applicants in Indonesia and applicants abroad may follow different practical preparation sequences.",
      options: {
        in_indonesia: "In Indonesia",
        abroad: "Outside Indonesia",
      },
    },
  },

  verdict: {
    bands: {
      strong_fit: {
        heading: "Your answers show a strong match",
        // FIXED-FROM-DECK #2 (terminology delta): the deck's draft was
        // "This is a preliminary fit assessment, not an approval." — the
        // deck's OWN "five hardest critiques" ban this exact word ("the
        // interface should consistently call it a 'fit-check result,'
        // never an eligibility certificate or assessment"). Reworded to
        // the deck's own mandated term.
        body: "Your age, intended route and stated financial position align with the core criteria presented in this fit-check. The next step is to verify your evidence and confirm the correct application path. This is a preliminary fit-check result, not an approval. The final decision rests with Imigrasi.",
      },
      likely_fit: {
        heading: "Your answers show a likely match",
        body: "The foundations appear to fit, but one or more details still need confirmation. We should review your funding evidence, property status or family plan before treating the route as settled. The final decision rests with Imigrasi.",
      },
      edge_case: {
        heading: "Your case needs human review",
        body: "Your answers fall into an area where a simple online verdict would be misleading. This may involve the 55–59 age disclosure band, property validation, incomplete funding or family circumstances. We will identify what is clear, what is uncertain and what evidence is needed next. The final decision rests with Imigrasi.",
      },
      not_eligible: {
        heading: "This route does not fit your current position",
        body: "Based on your answers, you do not currently meet the core financial or property conditions for this route. That is a route mismatch, not a personal judgment. You can review another visa category, reconsider the funding route or return when your circumstances change. The final decision rests with Imigrasi.",
      },
    },
    reasons: {
      propertyPendingStandard:
        "Property-route cases go through our property validation standard (addendum 007) before we can confirm fit — that keeps the review honest on both sides.",
      propertyDoesNotQualify:
        "Only a completed strata-title unit valued at USD 1,000,000 or more qualifies. Villas, land, leasehold, and off-plan purchases do not qualify for the property route.",
      unsureRoute:
        "You told us you're not sure which route fits — we evaluated the deposit route as a starting point. The comparison below can help you decide.",
      seniorBersyarat:
        "Senior routes are always reviewed case by case (bersyarat) — we never call these a strong match without a closer look.",
      seniorFundingUnclear:
        "We couldn't match your funding to either senior pattern yet. Let's talk through what you have — a deposit paired with income, or income alone.",
      seniorDepositStrong:
        "A USD 50,000 deposit paired with USD 3,000/month income matches the E33E senior pattern — a 5-year permit.",
      seniorIncomeOnlyStrong:
        "USD 3,000/month income alone matches the E33F senior pattern — a 1-year permit, with a 6-year cumulative cap.",
      // P2-C14: "and you're there" reads as an eligibility confirmation
      // (an arrival/conclusion idiom) rather than a preliminary fit-check
      // result — reworded to name what happens next instead of declaring
      // the applicant has arrived.
      depositReadyStrong:
        "USD 130,000, held in your own name at a state-owned (BUMN) Indonesian bank, is the core requirement for the base E33 deposit route — your answers align with it. We verify the evidence next.",
      capitalCloseVerify:
        "You're close to the USD 130,000 deposit threshold. Let's verify the exact figure with you — the deposit must be the full USD 130,000, held in your own name at a state-owned (BUMN) Indonesian bank.",
      capitalBelowThreshold:
        "The base E33 deposit route asks for USD 130,000, held in your own name at a state-owned (BUMN) Indonesian bank. What you've told us is below that threshold today.",
      seniorRoutesExistNote:
        "If you're 55 or older, senior routes exist with different funding patterns — your free fit memo can map the alternatives that might fit you.",
      incompleteAnswers:
        "We're missing an answer we need to give you an honest fit-check result. Please complete the question above, or start over if you followed a saved link.",
    },
    humanReview: {
      age5559Disclosure:
        "Indonesian regulation states this age threshold differently across articles — one reads 55, another reads 60. We operate on 55 with a signed client disclosure, and every case in this band gets a human review before we proceed.",
    },
  },

  custody: {
    eyebrow: "Your money stays yours",
    intro:
      "The deposit is evidence of your financial capacity. It is not a payment to Bali Zero.",
    steps: {
      step1: {
        title: "Open an account in your own name",
        body: "Your qualifying funds are placed in an account held in your own name at a state-owned (BUMN) Indonesian bank.",
      },
      step2: {
        title: "Use the bank evidence for your application",
        body: "You provide the required bank evidence so your financial eligibility can be reviewed. Bali Zero does not take custody of the deposit.",
      },
      step3: {
        // Copy-deck critique #2, binding: "ownership does not mean
        // unrestricted use" — this warning stays, always.
        title: "Maintain the qualifying position",
        body: "The funds remain legally yours, but withdrawing or moving them may affect your continuing compliance. Confirm the rules before changing the account or balance.",
      },
    },
    disclaimer:
      "Bank onboarding, account controls and acceptance of evidence remain subject to the bank and Imigrasi.",
  },

  routeComparator: {
    columns: {
      deposit: { title: "Deposit route" },
      property: { title: "Property route" },
      senior: { title: "Senior route (55+)" },
    },
    rows: {
      capital: {
        label: "Capital required",
        deposit: "USD 130,000 held on deposit, in your own name",
        property: "USD 1,000,000 completed strata-title property",
        senior:
          "USD 50,000 deposit plus USD 3,000/month income, or USD 3,000/month income only",
      },
      liquidity: {
        label: "Liquidity",
        deposit:
          "Your deposit stays yours, in your own name, for the life of the permit",
        property: "Capital is tied up in the property itself",
        senior:
          "Follows the liquidity profile of the matching deposit or income pattern",
      },
      whatQualifies: {
        label: "What qualifies",
        deposit: "A deposit at a state-owned (BUMN) Indonesian bank",
        property:
          "Only a completed strata-title unit — villas, land, leasehold, and off-plan do not qualify",
        senior: "Age 55 or older, with a matching funding pattern",
      },
      currentStatus: {
        label: "Current status",
        deposit: "Open",
        property: "Pending our property validation standard",
        senior: "Open, with a signed disclosure for ages 55-59",
      },
    },
  },

  timeline: {
    ownerLabels: {
      you: "You",
      balizero: "Bali Zero",
      imigrasi: "Imigrasi",
    },
    steps: {
      documents: {
        title: "Gather your documents",
        range: {
          local:
            "Typically 1-2 weeks if you're already in Indonesia — typical, not a promise.",
          abroad:
            "Typically a bit longer from abroad, once authentication and shipping are factored in — typical, not a promise.",
        },
        pace: {
          asap: "You're ready to move quickly — start gathering documents as soon as you can.",
          this_quarter:
            "A steady pace works well here — most clients finish this step within a few weeks.",
          exploring:
            "No rush — read through what's needed and start whenever you're ready.",
        },
      },
      bankDeposit: {
        title: "Open the account and place the deposit",
        range:
          "Timing varies by bank and their own KYC process — typical, not a promise.",
      },
      // P1-C9: buildTimeline swaps this second step by route/product — the
      // bank-deposit step above used to render unconditionally, telling a
      // property applicant or an E33F (income-only, explicitly "without
      // the deposit") applicant to place a deposit they were never asked
      // for.
      propertyEvidence: {
        title: "Provide your property evidence",
        range:
          "Timing depends on our pending property validation standard (addendum 007), once published — typical, not a promise.",
      },
      incomeEvidence: {
        title: "Prepare your income evidence",
        range:
          "Timing depends on gathering and verifying your income documentation — typical, not a promise.",
      },
      filing: {
        title: "We file your application",
        range:
          "Typically a matter of days once your documents and deposit are in place.",
      },
      imigrasiProcessing: {
        title: "Imigrasi reviews your file",
        range:
          "Several weeks, typically — this varies, and Imigrasi makes the final call.",
      },
      entryActivation: {
        title: "You enter Indonesia and activate the permit",
        range: "Scheduled once your visa is issued — typical, not a promise.",
      },
      first90Days: {
        title: "Your first 90 days",
        range:
          "A compliance duty we track for you during this window — typical, not a promise.",
      },
      annualLife: {
        title: "Living with your permit, year to year",
        range:
          "An ongoing rhythm of annual maintenance and renewal — typical, not a promise.",
      },
    },
  },

  checklist: {
    heading: "Documents worth preparing early",
    body: "This is a readiness list, not your final application checklist. We confirm the exact requirements after reviewing your route.",
    note: "Translations, legalisation or additional evidence may be required after human review.",
    items: {
      passportBioPage: {
        title: "Passport bio page",
        why: "To confirm your identity, nationality and passport details.",
      },
      passportValidity: {
        title: "Passport validity details",
        why: "To check whether your passport can support the intended permit period.",
      },
      passportPhoto: {
        title: "Recent passport-style photograph",
        why: "To prepare an image that meets the application format.",
      },
      residentialAddress: {
        title: "Current residential address",
        why: "To keep your personal details consistent across the application.",
      },
      personalHistory: {
        title: "Curriculum vitae or personal history",
        why: "To provide a clear account of your professional and personal background.",
      },
      bankDepositEvidence: {
        title: "Bank account and deposit evidence",
        why: "To verify a qualifying deposit held in your own name at a state-owned (BUMN) Indonesian bank.",
      },
      passiveIncomeEvidence: {
        title: "Passive-income evidence",
        why: "To verify the source, amount and regularity of income for a senior route.",
      },
      propertyDocuments: {
        title: "Completed strata-title property documents",
        why: "To assess ownership, completion, title type and value under our pending property validation standard.",
      },
      familyRecords: {
        title: "Marriage and birth records",
        why: "To document relationships if you want to include a spouse, children or parents.",
      },
      existingVisaPermit: {
        title: "Existing Indonesian visa or permit",
        why: "To identify any status, timing or transition issue if you are already in Indonesia.",
      },
    },
    readiness: {
      preparedLabel: "prepared",
      caption: "This tracks preparation, not approval odds.",
    },
  },

  price: {
    label: "Your all-inclusive figure",
    // P2-2: "nothing added later" contradicted the dependentsNote right
    // below it (dependents ARE priced separately, in the free fit memo) —
    // scoped the claim to the main applicant instead of dropping it.
    note: "One figure, everything included for the main applicant.",
    dependentsNote:
      "Dependents are priced in your free fit memo, not shown here.",
  },

  whatsapp: {
    button: "Ask us to review my plan",
    // P0-C3(c)/P1-B: mirrors the EXACT <=6 bullets
    // `whatsapp-bullets.ts::buildWhatsAppBullets` sends (Route, Age band,
    // Funding position, Family, Timing, Fit-check result) — no plan link,
    // no readiness row. The previous 8-field template (ageBand/route/
    // funding/property/family/timeline/location/verdict) had already
    // drifted from the implementation before this fix; this is the single
    // template both agree with going forward.
    prefillTemplate:
      "Hello Bali Zero. I completed the Second Home Studio fit-check.\n\n" +
      "Route: {{route}}\n" +
      "Age band: {{ageBand}}\n" +
      "Funding position: {{funding}}\n" +
      "Family: {{family}}\n" +
      "Timing: {{timing}}\n" +
      "Fit-check result: {{verdict}}\n\n" +
      "I understand this is a preliminary fit-check and that the final decision rests with Imigrasi. Please review the route and tell me what evidence you need next.",
    // P0-C3(c)/P1-B: the old sentence ("Only the answers shown above will
    // be added to your message") under-described what actually happens —
    // WhatsAppLeadButton POSTs a lead capture (this same summary) BEFORE
    // the wa.me redirect, and the previous copy said nothing about that.
    // Rewritten to name both the capture and the pre-fill honestly.
    privacy:
      "Tapping the button shares this summary with Bali Zero so we can prepare your review, and opens WhatsApp with the same summary pre-filled — check it before you send.",
    note: "We don't collect your name or email here — WhatsApp is the only handoff.",
  },

  savePlanBar: {
    heading: "Keep your plan for later",
    body: "Your saved plan stays on this device unless you copy and share its link.",
    saveButton: "Save on this device",
    savedConfirmation: "Plan saved on this device",
    copyLinkButton: "Copy plan link",
    copiedConfirmation: "Plan link copied",
    printButton: "Print / Save as PDF",
    linkWarning:
      "Anyone who receives the link may be able to view the answers it contains.",
    clearButton: "Clear saved plan",
  },
} as const;

/**
 * Dot-path resolver: `getCopy("verdict.bands.strong_fit.heading")`.
 * Never throws — an unresolved path (typo, drift between rules.ts and this
 * module, a key that doesn't exist yet) returns the key itself so a broken
 * reference is visible in the UI instead of crashing the render.
 */
export function getCopy(key: string): string {
  const parts = key.split(".");
  let node: unknown = COPY;
  for (const part of parts) {
    if (
      typeof node !== "object" ||
      node === null ||
      !Object.prototype.hasOwnProperty.call(node, part)
    ) {
      return key;
    }
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : key;
}

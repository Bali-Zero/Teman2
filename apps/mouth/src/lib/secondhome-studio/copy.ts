/**
 * Second Home Studio — ALL user-visible copy for the studio, in one module.
 *
 * Every component references keys via `getCopy("dot.path")`, never inline
 * strings. This makes `__tests__/forbidden-claims.test.ts` a complete sweep:
 * it walks every string value in COPY recursively and asserts none matches
 * the forbidden-claim patterns from SPEC-secondhome-studio-phaseB.md §6.
 *
 * Hard rules baked into every string here (spec §0/§6 — non-negotiable):
 *  - Always "state-owned (BUMN) Indonesian bank" — never "any bank".
 *  - Always "in your own name" / "your own name" for the deposit.
 *  - "non-working residency" is the only way we describe the permit's work
 *    status — never "work locally" / "work in Indonesia" in any order, even
 *    negated, because the forbidden-claims sweep matches on the substring,
 *    not the sentence's polarity.
 *  - "the final decision rests with Imigrasi" appears verbatim in every
 *    verdict band body.
 *  - No LPS, no BSI, no sharia, no split-deposit phrasing, no guaranteed/
 *    100% approval, no automatic ITAP/permanent conversion, no "5-10 years"
 *    for base E33 (it's "up to 5 years, renewable, 10-year cumulative cap"
 *    — the two numbers never sit adjacent to a dash), no IDR 2,000,000, no
 *    E33S/E33R codes (E33E/E33F are fine — different letters).
 *  - Never a price literal: the figure renders only from usePricingData.
 *  - Property route never reads as a green "qualified" — always the
 *    validation-standard note, always Edge-case upstream in rules.ts.
 *  - Dependents: "priced in your free fit memo", never a number here.
 *
 * Tone: calm, factual, second person, no hype, no urgency, no scarcity.
 */

export const COPY = {
  wizard: {
    age: {
      heading: "How old are you?",
      body: "Indonesia's second-home framework treats age bands differently — this shapes which route fits you.",
      why: "Why we ask: the base E33 deposit route and the 55-and-older senior routes have different funding requirements. Your age decides which comparison we show you next.",
      options: {
        under_55: "Under 55",
        "55_59": "55 to 59",
        "60_plus": "60 or older",
      },
    },
    route: {
      heading: "Which route are you exploring?",
      body: "There are two ways to qualify for a Second Home permit: a deposit at a state-owned (BUMN) Indonesian bank, or a qualifying property. Pick the one you're leaning toward, or tell us you're not sure yet.",
      why: "Why we ask: the deposit and property routes have different capital requirements and a different verification path. If you're not sure, we'll show you both routes side by side.",
      options: {
        deposit: "Deposit route",
        property: "Property route",
        unsure: "I'm not sure yet",
      },
    },
    capital: {
      heading: "Where does your capital stand?",
      body: "The deposit route asks for USD 130,000, held in your own name at a state-owned (BUMN) Indonesian bank, for the life of the permit.",
      why: "Why we ask: your fit band depends on how close you are to the full amount.",
      options: {
        ready_130k: "I have USD 130,000 ready",
        close_100k_130k: "I have between USD 100,000 and USD 130,000",
        below_100k: "I have less than USD 100,000",
      },
    },
    seniorFunding: {
      heading: "How would you fund the senior route?",
      body: "At 55 and older, there are two funding patterns: a smaller deposit paired with monthly income, or income alone.",
      why: "Why we ask: each pattern maps to a different senior product, with a different permit length.",
      options: {
        deposit_50k_income: "USD 50,000 deposit plus USD 3,000/month income",
        income_only_3k: "USD 3,000/month income only",
        neither: "Neither of these fits my situation",
        not_applicable: "Not applicable to me",
      },
    },
    property: {
      heading: "What's the status of your property?",
      body: "Only a completed strata-title unit valued at USD 1,000,000 or more qualifies for the property route.",
      why: "Why we ask: villas, land, leasehold, and off-plan purchases don't qualify — we'd rather be upfront about that before you go further.",
      options: {
        owns_qualifying_strata: "I already own a qualifying strata-title unit",
        buying_completed_strata: "I'm buying a completed strata-title unit",
        villa_land_leasehold: "It's a villa, land, or leasehold property",
        none: "I don't have a qualifying property yet",
      },
    },
    family: {
      heading: "Who else is coming with you?",
      body: "Tell us about the family members you'd bring — this doesn't change your own fit, but it shapes what we prepare for you.",
      why: "Why we ask: dependent visas follow a separate process. We use this only to scope your fit memo.",
      spouseLabel: "Spouse",
      childrenLabel: "Children",
      parentsLabel: "Parents",
      dependentsNote:
        "Family members you add are priced in your free fit memo — there's no line-item cost shown here.",
    },
    horizon: {
      heading: "What's your timeline?",
      body: "This helps us set realistic expectations. None of the ranges you'll see are promises.",
      why: "Why we ask: it changes how we frame the steps ahead for you — it does not change how fast Imigrasi processes your file.",
      options: {
        asap: "As soon as possible",
        this_quarter: "This quarter",
        exploring: "Just exploring for now",
      },
    },
    location: {
      heading: "Where are you right now?",
      body: "Some steps move differently depending on whether you're already in Indonesia or coordinating from abroad.",
      why: "Why we ask: it changes the typical range for gathering and authenticating your documents.",
      options: {
        in_indonesia: "In Indonesia",
        abroad: "Abroad",
      },
    },
  },

  verdict: {
    bands: {
      strong_fit: {
        label: "Strong fit",
        body: "Based on what you've told us, you meet the core requirements we look for. This is our honest read, not a guarantee — the final decision rests with Imigrasi.",
      },
      likely_fit: {
        label: "Likely fit — worth verifying",
        body: "You're close, and a few details are worth verifying with us before we call this a strong fit. As with every case, the final decision rests with Imigrasi.",
      },
      edge_case: {
        label: "Edge case — needs a closer look",
        body: "Your situation falls into a category we review case by case, together with you. The final decision rests with Imigrasi.",
      },
      not_eligible: {
        label: "Not eligible on the base route today",
        body: "Based on what you've told us, the base E33 deposit route isn't a fit today, and there may be other routes worth exploring together. The final decision rests with Imigrasi.",
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
        "Senior routes are always reviewed case by case (bersyarat) — we never call these a strong fit without a closer look.",
      seniorFundingUnclear:
        "We couldn't match your funding to either senior pattern yet. Let's talk through what you have — a deposit paired with income, or income alone.",
      seniorDepositStrong:
        "A USD 50,000 deposit paired with USD 3,000/month income matches the E33E senior pattern — a 5-year permit.",
      seniorIncomeOnlyStrong:
        "USD 3,000/month income alone matches the E33F senior pattern — a 1-year permit, with a 6-year cumulative cap.",
      depositReadyStrong:
        "USD 130,000, held in your own name at a state-owned (BUMN) Indonesian bank, is the core requirement for the base E33 deposit route — and you're there.",
      capitalCloseVerify:
        "You're close to the USD 130,000 deposit threshold. Let's verify the exact figure with you — the deposit must be the full USD 130,000, held in your own name at a state-owned (BUMN) Indonesian bank.",
      capitalBelowThreshold:
        "The base E33 deposit route asks for USD 130,000, held in your own name at a state-owned (BUMN) Indonesian bank. What you've told us is below that threshold today.",
      seniorRoutesExistNote:
        "If you're 55 or older, senior routes exist with different funding patterns — your free fit memo can map the alternatives that might fit you.",
      incompleteAnswers:
        "We're missing an answer we need to give you an honest read. Please complete the question above, or start over if you followed a saved link.",
    },
    humanReview: {
      age5559Disclosure:
        "Indonesian regulation states this age threshold differently across articles — one reads 55, another reads 60. We operate on 55 with a signed client disclosure, and every case in this band gets a human review before we proceed.",
    },
  },

  custody: {
    step1: {
      title: "You open the account",
      body: "You open the account in your own name at a state-owned (BUMN) Indonesian bank.",
    },
    step2: {
      title: "Your deposit stays yours",
      body: "Your USD 130,000 deposit stays in that account, in your own name, for the life of the permit.",
    },
    step3: {
      title: "We prepare and file",
      body: "Bali Zero prepares and files your application. We are never in the chain of custody, and we never hold client funds.",
    },
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
    items: {
      passportValidity: {
        title: "Passport valid for at least 30 months",
        why: "Immigration needs enough runway on your passport to cover the permit period.",
      },
      passportScan: {
        title: "A clean passport scan",
        why: "A clear, full-page scan avoids back-and-forth during filing.",
      },
      proofOfFunds: {
        title:
          "Bank reference or proof-of-funds statement, in the right format",
        why: "The format matters as much as the amount — we'll confirm the exact template with you.",
      },
      personalStatement: {
        title: "A personal statement",
        why: "A short statement explaining your plans helps frame your application.",
      },
      photos: {
        title: "Passport-style photos",
        why: "A standard requirement across the filing.",
      },
      addressAbroad: {
        title: "Your current address abroad",
        why: "Used to confirm your residency status before the move.",
      },
      healthInsurance: {
        title: "Health insurance intent",
        why: "Not mandatory for filing, but worth having in place before you arrive.",
      },
      familyDocuments: {
        title: "Family documents, if you're bringing dependents",
        why: "Marriage and birth certificates are typically needed for dependent visas.",
      },
      travelPlan: {
        title: "A rough travel plan",
        why: "Helps us sequence entry and activation around your schedule.",
      },
      depositSource: {
        title: "Clarity on your deposit source",
        why: "Knowing where the funds are coming from now avoids delays at the bank later.",
      },
    },
    readiness: {
      preparedLabel: "prepared",
      caption: "This tracks preparation, not approval odds.",
    },
  },

  price: {
    label: "Your all-inclusive figure",
    note: "One figure, everything included — nothing decomposed, nothing added later.",
    dependentsNote:
      "Dependents are priced in your free fit memo, not shown here.",
  },

  whatsapp: {
    prefillTemplate:
      "Hi Bali Zero — I just finished the Second Home fit check.\n" +
      "Route: {route}\n" +
      "Result: {band}\n" +
      "Timeline: {horizon}\n" +
      "Family: {familySummary}\n" +
      "Readiness: {readiness}\n" +
      "My saved plan: {planUrl}",
    buttonLabel: "Continue on WhatsApp",
    note: "We don't collect your name or email here — WhatsApp is the only handoff.",
  },

  savePlanBar: {
    heading: "Your plan stays on this device",
    body: "We don't save your answers on our servers. Copy a link to pick it up later, on this device or another.",
    copyLinkButton: "Copy plan link",
    copiedConfirmation: "Link copied",
  },
} as const;

/**
 * Dot-path resolver: `getCopy("verdict.bands.strong_fit.label")`.
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

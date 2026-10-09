/**
 * Visa Oracle v2 — EN/ID copy dictionary.
 *
 * Deliberately NOT the global `src/i18n` provider (spec item 30 — avoids
 * the I18nProvider lint chain; this route is a standalone experience).
 * EN is the canonical key set; `id` is typed `Record<Keys, string>` so a
 * missing/extra key in Indonesian is a TypeScript error at build time
 * (`i18n.test.ts` re-checks this at runtime as defense-in-depth).
 *
 * ID register (design doc §3/§4): body-first, warm-formal, "Anda" never
 * "kamu", Imigrasi's own terminology natively — not machine-translated.
 */
import type { Language } from "./flow";

const en = {
  "framing.title": "A map, not an application",
  "framing.body":
    "Answer honestly, including “I don’t know.” Nothing here is filed, and this tool never chooses a visa for you.",
  "framing.cta": "Start",

  "q.in_indonesia": "Are you in Indonesia right now?",
  "q.in_indonesia.hint": "This decides which questions matter next.",
  "q.in_indonesia.opt.yes": "Yes, I’m here",
  "q.in_indonesia.opt.no": "No, I’m planning ahead",
  "why.in_indonesia":
    "Where you are now decides whether we look at permits you can get inside Indonesia or visas you apply for before travelling.",

  "q.permit_expiry": "When does your current stay permit expire?",
  "q.permit_expiry.hint":
    "The date on your visa or ITAS/KITAS — not your passport.",
  "q.permit_expiry.label": "Expiry date",
  "why.permit_expiry":
    "We need the actual date to judge how much time you have left. It is not used to pick a filing route for you.",
  "q.current_status_code": "What code appears on your current stay permit?",
  "q.current_status_code.hint":
    "Enter the exact printed code. Use Not sure rather than translating a permit name.",
  "q.current_status_code.label": "Current permit code",
  "q.current_status_code.opt.A1": "A1",
  "q.current_status_code.opt.C1": "C1",
  "q.current_status_code.opt.C2": "C2",
  "q.current_status_code.opt.C6": "C6",
  "q.current_status_code.opt.ITK_FROM_BVK": "ITK converted from BVK",
  "q.current_status_code.opt.ITK_FROM_VISIT_C": "ITK converted from Visit C",
  "q.current_status_code.opt.ITK_FROM_VISIT_D": "ITK converted from Visit D",
  "q.current_status_code.opt.ITK_PERALIHAN": "ITK Peralihan",
  "q.current_status_code.opt.other": "Another code — needs human review",
  "why.current_status_code":
    "We use the code exactly as printed on your permit. We never guess it from the permit’s name.",
  "q.holds_stay_permit":
    "Do you currently hold a limited or permanent stay permit (KITAS / KITAP)?",
  "why.holds_stay_permit":
    "The E-code catalogue only applies to KITAS/KITAP holders; everyone else answers the shorter code list below.",
  "q.stay_permit_code": "Which code is printed on your permit?",
  "q.stay_permit_code.hint":
    "Enter the exact code from your card. Use Not sure rather than guessing.",
  "q.stay_permit_code.opt.E23": "E23 — Working Visa",
  "q.stay_permit_code.opt.E23U":
    "E23U — Working Visa — Foreign Diplomat House Assistant",
  "q.stay_permit_code.opt.E23V":
    "E23V — Working Visa — Trade and Economic Office",
  "q.stay_permit_code.opt.E28A": "E28A — Investor Visa",
  "q.stay_permit_code.opt.E28B":
    "E28B — Investor Golden Visa — Company Establishment",
  "q.stay_permit_code.opt.E28C": "E28C — Investor Golden Visa — Capital Market",
  "q.stay_permit_code.opt.E28D":
    "E28D — Investor Golden Visa — Branch or Subsidiary",
  "q.stay_permit_code.opt.E28F":
    "E28F — Investor Golden Visa — New Capital (IKN) Subsidiary",
  "q.stay_permit_code.opt.E30": "E30 — Education Visa",
  "q.stay_permit_code.opt.E30A": "E30A — Primary/Secondary Education Visa",
  "q.stay_permit_code.opt.E30B": "E30B — Higher Education Visa",
  "q.stay_permit_code.opt.E30E": "E30E — SEZ Education Visa",
  "q.stay_permit_code.opt.E30F": "E30F — Student Exchange Visa",
  "q.stay_permit_code.opt.E31A":
    "E31A — Family Visa — Spouse of Indonesian Citizen",
  "q.stay_permit_code.opt.E31B":
    "E31B — Family Visa — Spouse of ITAS/ITAP Holder",
  "q.stay_permit_code.opt.E31C":
    "E31C — Family Visa — Child of Legal Mixed Marriage",
  "q.stay_permit_code.opt.E31D":
    "E31D — Family Visa — Stepchild of Foreigner in Legal Mixed Marriage",
  "q.stay_permit_code.opt.E31E":
    "E31E — Family Visa — Child of ITAS/ITAP Holder",
  "q.stay_permit_code.opt.E31F":
    "E31F — Family Visa — Child of Indonesian Citizen Parent",
  "q.stay_permit_code.opt.E31G":
    "E31G — Family Visa — Parent of Indonesian Citizen Child",
  "q.stay_permit_code.opt.E31H":
    "E31H — Family Visa — Parent of Child ITAS/ITAP Holder",
  "q.stay_permit_code.opt.E31J":
    "E31J — Family Visa — Child Joining Sibling ITAS/ITAP Holder",
  "q.stay_permit_code.opt.E33": "E33 — Second Home Visa",
  "q.stay_permit_code.opt.E33A":
    "E33A — Second Home Visa — Special-Expertise Government Invitation",
  "q.stay_permit_code.opt.E33B":
    "E33B — Second Home Golden Visa — Special-Expertise Collaboration",
  "q.stay_permit_code.opt.E33C":
    "E33C — Second Home Golden Visa — World-Figure Government Invitation",
  "q.stay_permit_code.opt.E33E":
    "E33E — Second Home Golden Visa — Elderly 5-Year",
  "q.stay_permit_code.opt.E33F": "E33F — Second Home Visa — Elderly 1-Year",
  "q.stay_permit_code.opt.E33G": "E33G — Second Home Visa — Remote Worker",
  "why.stay_permit_code":
    "We use the code exactly as printed, the same as in the code list above. We never guess it from the permit’s name.",

  "q.renewal_paid": "Have you paid for the renewal of this stay permit?",
  "q.renewal_paid.hint":
    "Answer about payment, not paperwork — this is separate from whether the renewal has been submitted.",
  "why.renewal_paid":
    "A renewal counts as filed once payment has been made, not once documents are submitted — a renewal-in-process holder stays on the permit they extended, the same as anyone else with an active permit.",

  "q.overstay_days": "How many overstay days are active right now?",
  "q.overstay_days.hint":
    "Enter 0 if there is no active overstay. Do not include past overstay history here.",
  "q.overstay_days.label": "Current overstay",
  "why.overstay_days":
    "Days of overstay are asked separately because they weigh heavily on what is possible. We never work them out from the expiry date.",
  "q.wants_onshore_conversion":
    "Are you asking to change status without leaving Indonesia?",
  "q.wants_onshore_conversion.hint":
    "Answer about your intended process, not whether it will be approved.",
  // Offshore wording (adversarial review 2026-09-06, finding 9). The same
  // question, asked of someone who is not in Indonesia yet: put in the
  // present tense it reads as a claim about a country they have not
  // reached. The fact sent to the engine is identical either way.
  "q.wants_onshore_conversion.offshore":
    "Once in Indonesia, do you plan to switch to a different permit without leaving the country?",
  "q.wants_onshore_conversion.offshore.hint":
    "Answer about the process you intend to follow after you arrive, not whether it will be approved.",
  "why.wants_onshore_conversion":
    "Your yes or no only tells us which process you intend to follow. It does not pick a conversion path for you.",
  "q.application_channel":
    "Which application channel are you actually pursuing?",
  "q.application_channel.hint":
    "Choose only a channel already confirmed for your case, or use Not sure.",
  "q.application_channel.opt.OFFSHORE": "Apply after leaving Indonesia",
  "q.application_channel.opt.ONSHORE_CONVERSION": "Onshore status conversion",
  "q.application_channel.opt.STATUS_BRIDGING": "Status bridging process",
  "why.application_channel":
    "We use the channel you choose as it is. We never assign one from your dates.",
  "q.application_channel.conflict":
    "That channel doesn’t match your earlier answer about changing status without leaving Indonesia. Go back and correct one of the two answers — we won’t guess which one is right.",

  "q.nationalities": "Which nationalities appear on your passports?",
  "q.nationalities.hint":
    "Choose each passport country. The stored answer remains a language-independent country code.",
  "q.nationalities.label": "Passport countries",
  "why.nationalities":
    "Nationality is checked exactly as you give it. Several nationalities are kept separate and never guessed.",
  "q.birth_date": "What is your date of birth?",
  "q.birth_date.hint":
    "Some visas have age rules; we use your date of birth only to check them.",
  "q.birth_date.label": "Date of birth",
  "why.birth_date":
    "Some visas treat adults and minors differently. Your age alone never decides whether you are eligible.",
  "q.guardian_consent":
    "Is a parent or legal guardian filling this in with you?",
  "q.guardian_consent.help":
    "We ask because the applicant is under 18. We record only your answer to this question — no name, no document, no contact details.",
  "why.guardian_consent":
    "An applicant under 18 cannot give this consent alone, so Bali Zero asks an adult to confirm they are present before the assessment continues.",

  "lane.expired.notice":
    "Your permit has already expired. Overstay is fixable. It is not the end of your story here — this always goes to a human, and we won’t alarm you with a number on this screen.",
  "lane.urgent.notice":
    "You have 1–2 days left. That’s too close for an automated check — a Bali Zero advisor needs to look at this today.",
  "lane.bridging.notice":
    "The date you entered is within seven days. We may pass your case to a Bali Zero consultant for review, and this tool will not choose a bridging or conversion route for you.",
  "lane.extend.notice":
    "You have time to compare Extend and Convert side by side.",
  "lane.planning.notice": "Plenty of runway — this is planning, not urgency.",

  "q.category": "What brings you to Indonesia?",
  "q.category.hint": "Pick the closest fit — you can refine it next.",
  // ENDING-ROUND E10: watershed WhyWeAsk sentence — same meaning, plainer.
  "why.category":
    "Your direction only chooses the next questions. It doesn’t decide whether a visa path is available — your answers do.",
  "q.category.opt.tourism": "Tourism & short visit",
  "q.category.opt.business": "Business (no work)",
  "q.category.opt.work": "Work & employment",
  "q.category.opt.invest": "Invest & golden",
  "q.category.opt.remote": "Remote worker",
  "q.category.opt.family": "Family & marriage",
  "q.category.opt.retirement": "Retirement",
  "q.category.opt.second_home": "Second Home",
  "q.category.opt.study": "Study",
  "q.category.opt.diaspora": "Diaspora & ex-WNI",
  "q.category.opt.other": "Something else",

  "q.boolean.yes": "Yes",
  "q.boolean.no": "No",
  "q.boolean.not_applicable": "Not applicable",
  "q.trip_scope": "Is this your only purpose for the trip?",
  "q.trip_scope.hint":
    "Choose multiple if work, family, study, business, or another purpose overlaps.",
  "q.trip_scope.opt.single": "Yes — one main purpose",
  "q.trip_scope.opt.multiple": "No — two or more purposes overlap",
  "why.trip_scope":
    "Overlapping purposes call for a consultant’s judgment, so this answer is not used to decide anything automatically.",
  "q.entry_pattern": "How do you expect to enter Indonesia?",
  "q.entry_pattern.hint": "Choose the pattern you are actually planning.",
  "q.entry_pattern.opt.SINGLE": "One entry",
  "q.entry_pattern.opt.MULTIPLE": "More than one entry",
  "why.entry_pattern":
    "We use your choice of single or multiple entry exactly as selected.",

  "q.sponsor_category": "Who sponsors your stay in Indonesia?",
  "q.sponsor_category.hint":
    "Choose the party that provides or backs your permit, not who pays your day-to-day bills.",
  "q.sponsor_category.opt.NONE": "No sponsor — I qualify on my own",
  "q.sponsor_category.opt.INDIVIDUAL":
    "An individual (a family or personal sponsor)",
  "q.sponsor_category.opt.EMPLOYER": "An employer — a company in Indonesia",
  "q.sponsor_category.opt.EDUCATION": "An educational institution",
  "q.sponsor_category.opt.INVESTMENT": "An investment or company I own",
  "q.sponsor_category.opt.GOVERNMENT": "A government body",
  "why.sponsor_category":
    "We note the kind of sponsor you have. No current rule uses it yet; this only prepares us for rules that will.",

  "q.sponsor_government_invitation":
    "Do you hold a written invitation from an Indonesian central-government body, issued to you for your special expertise?",
  "q.sponsor_government_invitation.hint":
    "Answer no if the invitation is not in writing yet, or does not come from an Indonesian central-government body.",
  "why.sponsor_government_invitation":
    "Only your yes or no about a government invitation is used here.",
  "q.sponsor_government_collaboration":
    "Do you have a confirmed collaboration commitment with an Indonesian government body or institution, based on your special expertise?",
  "q.sponsor_government_collaboration.hint":
    "A discussion or a proposal that is not confirmed yet counts as no.",
  "why.sponsor_government_collaboration":
    "Only your yes or no about a confirmed government collaboration is used here.",
  "q.sponsor_world_figure_invitation":
    "Has an Indonesian government body invited you as a world figure — a person of international standing?",
  "q.sponsor_world_figure_invitation.hint":
    "Answer yes only if a government body has invited you in that capacity.",
  "why.sponsor_world_figure_invitation":
    "Only your yes or no about a world-figure invitation is used here.",
  // One clause, not two: the wire fact `sponsor.diplomatic_household` is a
  // single boolean, and the earlier wording ("Is your employer a foreign
  // diplomat posted in Indonesia, AND is the role in that diplomat's
  // household?") asked the visitor to answer two things at once — a person who
  // works for a diplomat's embassy rather than the household could read either
  // half as the question (council round 6, council/journal.jsonl).
  "q.sponsor_diplomatic_household":
    "Is this a role in the household of a foreign diplomat posted in Indonesia?",
  "q.sponsor_diplomatic_household.hint":
    "Answer no if you would work for anyone other than the diplomat's own household.",
  "why.sponsor_diplomatic_household":
    "Only your yes or no about a diplomatic household role is used here.",
  "q.sponsor_trade_office":
    "Is your sponsor a foreign trade or economic representative office in Indonesia?",
  "q.sponsor_trade_office.hint":
    "Answer no if your sponsor is any other kind of organisation.",
  "why.sponsor_trade_office":
    "Only your yes or no about the sponsor being a trade office is used here.",
  "q.business_activity": "What will you mainly do on the business trip?",
  "q.business_activity.hint":
    "Describe the activity, not a visa name. Meetings, negotiation, conferences and looking into investing can be assessed here; training or another activity goes to a Bali Zero consultant for review.",
  "q.business_activity.opt.meetings": "Meetings or site visits",
  "q.business_activity.opt.negotiation": "Negotiation or signing",
  "q.business_activity.opt.conference": "Conference or trade event",
  "q.business_activity.opt.exploring":
    "Exploring whether to invest or open a business here",
  "q.business_activity.opt.training": "Giving or receiving training",
  "q.business_activity.opt.other": "Another business activity",
  "why.business_activity":
    "Exploring whether to invest or open a business is treated as an investment purpose, and we then ask the few questions that decide it. Any other answer here only decides whether a Bali Zero consultant has to look at your trip: training and “another business activity” do, the others do not.",
  "q.business_sponsor_confirmed":
    "Has a company sponsor or guarantor confirmed they will support the process?",
  "q.business_sponsor_confirmed.hint":
    "A conversation or possible partner is not a confirmed sponsor.",
  "why.business_sponsor_confirmed":
    "Whether your sponsor has confirmed is recorded as its own yes or no.",

  "q.work_payer":
    "Will an Indonesian-registered company employ and pay you here?",
  "q.work_payer.hint":
    "Not “do you need a work KITAS” — who actually pays you.",
  "why.work_payer":
    "We only use whether the employing entity is Indonesian. We do not pick a visa from it.",
  "q.work_payer.opt.yes": "Yes, an Indonesian entity pays me",
  "q.work_payer.opt.no": "No, I’m paid from abroad",

  "q.work_indonesia_compensation":
    "Will any compensation for this activity come from an Indonesian source?",
  "q.work_indonesia_compensation.hint":
    "Answer about the source of payment, not the currency or bank account.",
  "why.work_indonesia_compensation":
    "This tells us where your pay comes from. The amount and your eligibility are not worked out from it.",
  "q.work_sponsor_confirmed":
    "Has an Indonesian work sponsor confirmed they will support the process?",
  "q.work_sponsor_confirmed.hint":
    "A conversation or possible employer is not a confirmed sponsor.",
  "why.work_sponsor_confirmed":
    "Only your yes or no about the sponsor’s confirmation is used here.",

  "q.remote_clients": "Where do your clients or employer sit?",
  "q.remote_clients.hint":
    "This is what separates a remote-worker lane from a work lane.",
  "why.remote_clients":
    "We only use whether you serve Indonesian clients. We do not assume it from where you live.",
  "q.remote_clients.opt.foreign": "Abroad — they pay me from outside Indonesia",
  "q.remote_clients.opt.indonesian":
    "Indonesia — I’m effectively employed here",
  "q.remote_clients.opt.mixed": "A mix of both",

  "q.remote_compensation":
    "Will any remote-work compensation come from an Indonesian source?",
  "q.remote_compensation.hint":
    "This asks where payment originates, not how much you earn.",
  "why.remote_compensation":
    "The answer maps directly to work.indonesia_source_compensation.",
  "q.remote_employer_country":
    "Where is your remote employer or main client registered?",
  "q.remote_employer_country.hint":
    "Enter one two-letter ISO country code, for example IT.",
  "q.remote_employer_country.label": "Employer country code",
  "why.remote_employer_country":
    "We use the country code exactly as you enter it and do not interpret it.",
  "q.remote_pt_pma":
    "Is this remote-work plan tied to a committed Indonesian PT PMA?",
  "q.remote_pt_pma.hint":
    "Choose yes only for a real commitment, not a company you may form later.",
  "why.remote_pt_pma":
    "This maps directly to investment.pt_pma_committed and does not imply approval.",

  "q.investment_vehicle": "What is the concrete basis of your plan?",
  "q.investment_vehicle.hint": "This only decides which questions come next.",
  "q.investment_vehicle.opt.pt_pma": "A committed Indonesian PT PMA",
  "q.investment_vehicle.opt.property": "A qualifying property arrangement",
  "q.investment_vehicle.opt.bank_deposit": "A bank deposit in my own name",
  "q.investment_vehicle.opt.merit": "Merit, talent, or public contribution",
  "q.investment_vehicle.opt.family": "A family-linked route",
  "q.investment_vehicle.opt.capital_market":
    "Capital-market investments only, such as listed shares or bonds",
  "q.investment_vehicle.opt.undecided": "I have not chosen a basis yet",
  "why.investment_vehicle":
    "This only decides which questions we ask next. It never chooses a visa path.",
  "q.investment_currency": "Which currency can you commit an amount in?",
  "q.investment_currency.hint":
    "This only decides which amount question comes next. No conversion is ever performed between currencies.",
  "q.investment_currency.opt.idr": "Indonesian rupiah (IDR)",
  "q.investment_currency.opt.usd": "US dollars (USD)",
  "q.investment_currency.opt.still_unsure": "I can't say yet",
  "why.investment_currency":
    "This only chooses which amount question follows. It never chooses a visa path, and no figure is converted between currencies.",
  "q.investment_pt_pma": "Is the PT PMA commitment already concrete?",
  "q.investment_pt_pma.hint":
    "Answer no for an idea, early discussion, or uncommitted plan.",
  "why.investment_pt_pma":
    "We only note whether your commitment is concrete. No amount or status is assumed from it.",
  "q.investment_capital_idr": "What investment capital is committed?",
  "q.investment_capital_idr.hint":
    "Enter the exact whole-rupiah amount you can support with evidence.",
  "q.investment_capital_idr.label": "Committed investment capital",
  "why.investment_capital_idr":
    "The amount is used exactly as you enter it. No threshold is shown or assumed here.",
  "q.investment_amount_usd":
    "What investment amount is committed, in US dollars?",
  "q.investment_amount_usd.hint":
    "Enter the exact whole-dollar amount you can support with evidence.",
  "q.investment_amount_usd.label": "Committed investment amount",
  "why.investment_amount_usd":
    "The amount is used in the currency you chose. No threshold is shown or assumed here, and nothing is converted.",
  "q.investment_paid_up_capital_idr":
    "How much paid-up capital is already documented?",
  "q.investment_paid_up_capital_idr.hint":
    "Enter a whole-rupiah amount; use Not sure rather than estimating.",
  "q.investment_paid_up_capital_idr.label": "Documented paid-up capital",
  "why.investment_paid_up_capital_idr":
    "The paid-up amount is kept separate from your planned investment capital.",
  "q.investment_role": "What role would you hold in the company?",
  "q.investment_role.hint": "Choose the exact proposed-role description.",
  "q.investment_role.opt.SHAREHOLDER_DIRECTOR": "Shareholder and director",
  "q.investment_role.opt.SHAREHOLDER_COMMISSIONER":
    "Shareholder and commissioner",
  "q.investment_role.opt.EMPLOYEE": "Employee",
  "q.investment_role.opt.NO_OPERATIONAL_ROLE": "No operational role",
  "q.investment_role.opt.OTHER": "Another role",
  "why.investment_role": "The role you choose is used exactly as selected.",
  "q.investment_establishes_company":
    "Will you establish a company in Indonesia as part of this investment?",
  "q.investment_establishes_company.hint":
    "A subsidiary set up in Indonesia, including one of a company abroad, counts as a company. Answer no if the investment does not involve setting up a company in Indonesia.",
  "why.investment_establishes_company":
    "Only your yes or no about establishing a company is used here.",
  "q.investment_foreign_branch":
    "Are you establishing a branch or a subsidiary of a company that already exists outside Indonesia?",
  "q.investment_foreign_branch.hint":
    "Answer no if the company does not already exist outside Indonesia.",
  "why.investment_foreign_branch":
    "Only your yes or no about a branch or subsidiary of a foreign company is used here.",
  "q.investment_ikn_subsidiary":
    "Will the company you are establishing be a subsidiary located in the new capital, IKN (Ibu Kota Nusantara)?",
  "q.investment_ikn_subsidiary.hint":
    "Answer no for a company located anywhere else in Indonesia.",
  "why.investment_ikn_subsidiary":
    "Only your yes or no about a subsidiary in IKN is used here.",
  "q.investment_capital_market_only":
    "Is your investment held only in capital-market instruments, without establishing a company?",
  "q.investment_capital_market_only.hint":
    "Answer no if any part of the investment is outside the capital market.",
  "why.investment_capital_market_only":
    "Only your yes or no about a capital-market-only investment is used here.",
  "q.investment_meets_threshold":
    "Does your investment meet every published financial minimum for the route you chose — the capital amount, and the annual turnover where that route publishes one?",
  "q.investment_meets_threshold.hint":
    "If you do not know the published minimum for your route, answer no: the Oracle never assumes it is met.",
  "why.investment_meets_threshold":
    "Only your yes or no is used here. No amount is shown or assumed here.",
  "q.unit.idr": "IDR",
  "q.unit.usd": "USD",
  "q.unit.usd_month": "USD per month",

  "q.family_relation": "How are you related to the proposed sponsor?",
  "q.family_relation.hint": "Choose the relationship that can be documented.",
  "q.family_relation.opt.SPOUSE": "Spouse",
  "q.family_relation.opt.CHILD": "Child",
  "q.family_relation.opt.PARENT": "Parent",
  "q.family_relation.opt.SIBLING": "Sibling",
  "q.family_relation.opt.DEPENDENT": "Other dependent",
  "q.family_relation.opt.STEPCHILD": "Stepchild",
  "q.family_relation.opt.OTHER": "Another relationship",
  "why.family_relation": "Your relationship is used exactly as selected.",
  "q.marital_status": "What is your current marital status?",
  "q.marital_status.hint": "Choose your current legal status.",
  "q.marital_status.opt.SINGLE": "Single",
  "q.marital_status.opt.MARRIED": "Married",
  "q.marital_status.opt.DIVORCED": "Divorced",
  "q.marital_status.opt.WIDOWED": "Widowed",
  "q.marital_status.opt.OTHER": "Another status",
  "why.marital_status": "Your marital status is used exactly as selected.",
  "q.family_sponsor_nationalities":
    "Which nationalities appear on your sponsor’s passports?",
  "q.family_sponsor_nationalities.hint":
    "Choose each passport country. The answer stays separate from your own nationalities.",
  "q.family_sponsor_nationalities.label": "Sponsor passport countries",
  "why.family_sponsor_nationalities":
    "Your sponsor’s nationality is asked separately and is never copied from your own passports.",
  "q.family_sponsor_status_code":
    "Which stay permit does your sponsor currently hold?",
  "q.family_sponsor_status_code.hint":
    "Choose the option printed on your sponsor’s KITAS/KITAP card — this asks about your sponsor’s permit, not your own status. Choose “I’m not sure” if you cannot confirm it.",
  "why.family_sponsor_status_code":
    "Confirms your sponsor already holds a qualifying stay permit before we name a family visa product for you.",
  "q.family_sponsor_permit_basis":
    "What is the basis of your sponsor's own stay permit?",
  "q.family_sponsor_permit_basis.hint":
    "Choose the closest match to what your sponsor's Indonesian stay permit is for.",
  "q.family_sponsor_permit_basis.opt.EXPERT": "Expert",
  "q.family_sponsor_permit_basis.opt.WORKER": "Sponsored worker",
  "q.family_sponsor_permit_basis.opt.MARITIME_CREW": "Maritime crew",
  "q.family_sponsor_permit_basis.opt.CLERGY": "Religious worker (clergy)",
  "q.family_sponsor_permit_basis.opt.FOREIGN_INVESTMENT": "Foreign investor",
  "q.family_sponsor_permit_basis.opt.SCIENTIFIC_RESEARCH":
    "Scientific researcher",
  "q.family_sponsor_permit_basis.opt.EDUCATION": "Student",
  "q.family_sponsor_permit_basis.opt.FAMILY_REUNIFICATION":
    "Family reunification",
  "q.family_sponsor_permit_basis.opt.REPATRIATION":
    "Repatriation (former Indonesian citizen)",
  "q.family_sponsor_permit_basis.opt.SECOND_HOME": "Second Home visa holder",
  "q.family_sponsor_permit_basis.opt.MEDICAL_TREATMENT": "Medical treatment",
  "q.family_sponsor_permit_basis.opt.WORKING_HOLIDAY": "Working holiday",
  "q.family_sponsor_permit_basis.opt.OTHER": "Another basis",
  "why.family_sponsor_permit_basis":
    "Some permit bases block a family-reunification permit from being layered on top of them. We can't verify your answer automatically, so our team reviews it directly rather than the system deciding on its own.",
  "q.family_marriage_registered": "Is the marriage officially registered?",
  "q.family_marriage_registered.hint":
    "If your sponsor is your parent, this asks about your parents' marriage. Choose Not applicable if the family relationship involves no marriage.",
  "why.family_marriage_registered":
    "We use your answer as given — yes, no or not sure. We do not assume whether the marriage is registered.",
  "q.family_stepchild_marriage_certificate_confirmed":
    "Can you provide the marriage certificate of your Indonesian parent and their foreign spouse?",
  "q.family_stepchild_marriage_certificate_confirmed.hint":
    "This is the marriage certificate for the mixed Indonesian–foreign marriage the stepchild relationship comes from.",
  "why.family_stepchild_marriage_certificate_confirmed":
    "We ask about this document directly. It is not assumed from your answer about the marriage being registered above.",
  "q.family_stepchild_birth_certificate_confirmed":
    "Can you provide the stepchild's birth certificate?",
  "q.family_stepchild_birth_certificate_confirmed.hint":
    "The birth certificate should show the biological parent who is part of the mixed marriage.",
  "why.family_stepchild_birth_certificate_confirmed":
    "Birth-certificate evidence is recorded as its own yes or no.",
  "q.family_sponsor_confirmed":
    "Has the family sponsor confirmed they will support the process?",
  "q.family_sponsor_confirmed.hint":
    "Choose yes only after the sponsor has agreed.",
  "why.family_sponsor_confirmed":
    "Your sponsor’s confirmation is recorded as its own yes or no.",
  "q.retirement_penjamin_confirmed":
    "Do you have a penjamin — a licensed visa agency or a person in Indonesia — who will sponsor your retirement KITAS?",
  "q.retirement_penjamin_confirmed.hint":
    "If not, Bali Zero can act as your penjamin.",
  "why.retirement_penjamin_confirmed":
    "The penjamin’s confirmation is recorded as its own yes or no.",

  "q.retirement_basis": "Which basis can you document today?",
  "q.retirement_basis.hint":
    "This only selects the next factual questions; it does not choose a visa.",
  "q.retirement_basis.opt.bank_deposit": "A bank deposit in my own name",
  "q.retirement_basis.opt.property": "A property arrangement",
  "q.retirement_basis.opt.passive_income": "Regular passive monthly income",
  "q.retirement_basis.opt.family_sponsor": "A confirmed family sponsor",
  "q.retirement_basis.opt.undecided": "I have not chosen a basis",
  "why.retirement_basis":
    "This only decides which questions come next. It is not used for anything else.",
  "q.retirement_undecided_basis": "Which of these can you document today?",
  "q.retirement_undecided_basis.hint":
    "Pick whichever basis you can support with evidence. If neither applies, say so — a person is not needed to answer that.",
  "q.retirement_undecided_basis.opt.deposit_or_income":
    "A bank deposit or documented passive income",
  "q.retirement_undecided_basis.opt.family_sponsor":
    "A confirmed family sponsor",
  "q.retirement_undecided_basis.opt.still_unsure": "I still can't say",
  "why.retirement_undecided_basis":
    "This also only decides which questions come next, the same as the basis question above.",
  "q.secondhome_basis": "Which Second Home basis can you document today?",
  "q.secondhome_basis.hint":
    "Pick the one you can evidence now. Use Not sure rather than guessing.",
  "q.secondhome_basis.opt.bank_deposit": "A bank deposit held in my own name",
  "q.secondhome_basis.opt.property": "A qualifying property",
  "why.secondhome_basis":
    "This only decides which evidence questions follow. We use the evidence you give, not this choice.",
  "q.secondhome_deposit_usd": "What bank deposit can you document?",
  "q.secondhome_deposit_usd.hint":
    "Enter the exact whole-dollar amount; use Not sure rather than estimating.",
  "q.secondhome_deposit_usd.label": "Documented bank deposit",
  "why.secondhome_deposit_usd":
    "We use the exact amount you give. No threshold is shown here.",
  "q.secondhome_state_bank":
    "Is the deposit held at an Indonesian state-owned bank?",
  "q.secondhome_state_bank.hint": "Answer from the bank documentation.",
  "why.secondhome_state_bank":
    "Your yes or no is recorded separately from the deposit amount.",
  "q.secondhome_own_name": "Is the full deposit held in your own name?",
  "q.secondhome_own_name.hint": "Do not combine accounts or account holders.",
  "why.secondhome_own_name":
    "Your yes or no is recorded separately. We never assume ownership.",
  "q.secondhome_property_value_usd":
    "What property value can you document for this plan?",
  "q.secondhome_property_value_usd.hint":
    "Enter the exact whole-dollar value supported by documents.",
  "q.secondhome_property_value_usd.label": "Documented property value",
  "why.secondhome_property_value_usd":
    "We use the exact value you give. Ownership and tenure are not assumed.",
  "q.secondhome_passive_income_usd":
    "What passive monthly income can you document?",
  "q.secondhome_passive_income_usd.hint":
    "Enter the exact whole-dollar monthly amount.",
  "q.secondhome_passive_income_usd.label": "Documented passive income",
  "why.secondhome_passive_income_usd":
    "The monthly amount is used as you enter it and is never estimated from your assets.",

  "q.study_level": "What level of study are you planning?",
  "q.study_level.hint": "Choose the level shown by the institution.",
  "q.study_level.opt.PRIMARY": "Primary school",
  "q.study_level.opt.SECONDARY": "Secondary school",
  "q.study_level.opt.VOCATIONAL": "Vocational programme",
  "q.study_level.opt.UNDERGRADUATE": "Undergraduate degree",
  "q.study_level.opt.POSTGRADUATE": "Postgraduate degree",
  "q.study_level.opt.RESEARCH": "Research",
  "q.study_level.opt.OTHER": "Another level",
  "why.study_level": "Your study level is used exactly as selected.",
  "q.study_admission_confirmed":
    "Has an Indonesian institution confirmed your admission?",
  "q.study_admission_confirmed.hint":
    "An application in progress is not confirmed admission.",
  "why.study_admission_confirmed":
    "Admission confirmation is recorded as its own yes or no.",
  "q.study_sponsor_confirmed":
    "Has the institution or study sponsor confirmed support?",
  "q.study_sponsor_confirmed.hint":
    "Choose yes only if the sponsor has agreed.",
  "why.study_sponsor_confirmed":
    "Sponsor confirmation is recorded separately from admission.",

  "q.diaspora_connection": "What is your connection to Indonesia?",
  "q.diaspora_connection.hint":
    "This is context for our team only. Your nationality is asked separately.",
  "q.diaspora_connection.opt.former_wni": "I am a former Indonesian citizen",
  "q.diaspora_connection.opt.descendant":
    "I am a descendant of an Indonesian citizen",
  "q.diaspora_connection.opt.dual":
    "I may hold or have held more than one citizenship",
  "q.diaspora_connection.opt.family": "My connection is through family",
  "q.diaspora_connection.opt.other": "Another connection",
  "why.diaspora_connection":
    "No rule is based on a diaspora connection, so this answer is kept only as context for our team.",
  "q.diaspora_documents": "Can you document that connection?",
  "q.diaspora_documents.hint":
    "Do not upload documents here; answer only whether evidence exists.",
  "why.diaspora_documents":
    "This is human context only and cannot improve automated eligibility.",

  "q.other_purpose": "Which activity is closest to your plan?",
  "q.other_purpose.hint":
    "This context is not turned into a purpose or a visa choice.",
  "q.other_purpose.opt.transit": "Transit",
  "q.other_purpose.opt.medical": "Medical treatment or support",
  "q.other_purpose.opt.volunteer": "Volunteer activity",
  "q.other_purpose.opt.religious": "Religious activity",
  "q.other_purpose.opt.arts_sport": "Arts or sport",
  "q.other_purpose.opt.journalism": "Journalism or media",
  "q.other_purpose.opt.crew": "Transport crew",
  "q.other_purpose.opt.other": "Something not listed",
  "why.other_purpose":
    "No single rule matches these options, so the answer stays as context for our team.",
  "q.other_paid_activity": "Will any part of this activity be paid?",
  "q.other_paid_activity.hint":
    "This is context for our team only. It is not turned into an employment answer.",
  "why.other_paid_activity":
    "No exact rule fits this broad question, so the answer cannot support a recommendation.",

  "q.stay_days": "How many days do you plan to stay?",
  "q.stay_days.hint":
    "Enter the planned total as a whole number; this is not a legal threshold.",
  "q.stay_days.label": "Planned stay",
  "q.stay_days.unit": "days",
  "why.stay_days":
    "We check your exact planned stay instead of guessing from a broad range.",

  "q.review_gate": "Is there anything else we should know?",
  // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M6): the lead no longer promises
  // a human review that no longer happens after A1'/A3-B — see A5's
  // `outcome.disclaimer.complex_to_human` for the same underlying fact.
  "q.review_gate.hint":
    "Tick everything that applies — an omission costs you more than a disclosure. Some of these, a criminal record among them, put your case in front of a person before any verdict; the others are attached to your result as conditions our team checks with you before submission.",
  "why.review_gate":
    "Every item here is taken into account: the three immigration-history ones bear directly on the rules, and all of them must be reflected in your result.",
  "q.review_gate.opt.none": "None of these apply to me",
  "q.review_gate.opt.flagged": "One or more applies",
  // Finding #5 (adversarial review 2026-07-17): "none" is now a first-class
  // checklist item (REVIEW_GATE_ITEMS[0] in tree.ts), mutually exclusive
  // with the real flags below — this is its checklist label.
  "q.review_gate.item.none": "None of these apply to me",
  "q.review_gate.item.criminal_record": "A criminal record, anywhere",
  "q.review_gate.item.health_flag":
    "A health condition immigration may ask about",
  "q.review_gate.item.prior_refusal": "A prior visa refusal or denial",
  "q.review_gate.item.overstay": "A past overstay",
  "q.review_gate.item.blacklist": "A blacklist entry",
  "q.review_gate.item.immigration_investigation":
    "An immigration investigation",
  "q.review_gate.item.pep_or_sanctions":
    "A politically exposed person or sanctions concern",
  "q.review_gate.item.source_of_funds_unclear":
    "Unclear or incomplete source-of-funds evidence",
  "q.review_gate.item.diplomatic_passport": "A diplomatic passport",
  "q.review_gate.item.ambiguous_sponsor":
    "The proposed sponsor is not yet clear",
  "q.review_gate.item.activity_boundary":
    "The planned activity may cross more than one category",
  "q.review_gate.item.not_certain": "I’m not certain about any of the above",
  "q.review_gate.none_selected": "None of these apply to me",

  "notsure.trigger": "Not sure?",
  "assumption.in_indonesia":
    "You weren’t sure where you are, so we recorded that as unresolved instead of assuming it, and a Bali Zero advisor confirms it with you.",
  "assumption.permit_expiry":
    "You weren’t sure when your current stay permission expires, so no deadline was inferred.",
  "assumption.stay_days":
    "You weren’t sure about the planned stay, so no duration was inferred.",
  "assumption.work_payer":
    "You weren’t sure who pays you, so we recorded that as unresolved; we still assessed everything we could, and a Bali Zero advisor confirms this point with you.",
  "assumption.remote_clients":
    "You weren’t sure where your clients sit, so we recorded that as unresolved; we still assessed everything we could, and a Bali Zero advisor confirms this point with you.",
  "assumption.secondhome_deposit_usd":
    "You weren’t sure what bank deposit you can document, so we assessed this plan as if the deposit were zero; a Bali Zero advisor confirms the real figure with you.",
  "assumption.secondhome_property_value_usd":
    "You weren’t sure what property value you can document, so we assessed this plan as if the property value were zero; a Bali Zero advisor confirms the real figure with you.",
  "assumption.secondhome_passive_income_usd":
    "You weren’t sure what passive monthly income you can document, so we assessed this plan as if that income were zero; a Bali Zero advisor confirms the real figure with you.",
  "assumption.secondhome_state_bank":
    "You weren’t sure whether the deposit sits at an Indonesian state-owned bank, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  "assumption.secondhome_own_name":
    "You weren’t sure whether the full deposit is held in your own name, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  "assumption.study_admission_confirmed":
    "You weren’t sure whether an Indonesian institution has confirmed your admission, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  "assumption.study_sponsor_confirmed":
    "You weren’t sure whether the institution or study sponsor has confirmed support, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  "assumption.diaspora_documents":
    "You weren’t sure whether you can document that connection, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  "assumption.retirement_basis":
    "You weren’t sure which basis you can document today, so we assessed this plan as if you had not chosen a basis yet; a Bali Zero advisor confirms it with you.",
  "assumption.retirement_penjamin_confirmed":
    "You weren’t sure whether you have a penjamin, so we assessed this plan as if the answer were “no”; Bali Zero can act as your penjamin.",
  "assumption.generic":
    "You marked “Not sure” for “{{question}}”; no value was inferred.",

  "whyweask.trigger": "Why we ask",
  "whyweask.trigger.aria": "Why we ask this question",
  "whyweask.fact_prefix": "Used to decide: {{facts}}",
  "whyweask.review_only":
    "Flagged for review; only these details are used: {{facts}}",
  "whyweask.human_context":
    "For our team’s context only — not used to decide anything.",

  "back.button": "Back",
  "question.continue": "Continue",
  "question.human_context_notice":
    "Human context only — this answer cannot select, rank, add, or remove a visa path.",
  "question.invalid_country_codes":
    "Choose a country from the verified list, or select Not listed.",
  "question.country_picker.placeholder": "Choose a country",
  "question.country_picker.search": "Search countries",
  "question.country_picker.search_placeholder": "Type a country name…",
  "question.country_picker.not_listed": "Other / not listed",
  "question.country_picker.add": "Add country",
  "question.country_picker.selected": "Selected countries",
  "question.country_picker.remove": "Remove {{country}}",
  "question.country_picker.max":
    "You can add up to {{count}} passport countries. Remove one to choose another.",
  "question.invalid_status_code":
    "Enter the exact permit code shown on the document, using letters and numbers only.",
  "restart.button": "Start over",
  "verdict.edit_answers": "Edit answers",

  "tree.edit_aria": "Edit answer: {{question}}",
  "tree.breadcrumb_label": "Current interview branch",
  "tree.framing": "Start",
  "tree.in_indonesia": "Where you are",
  "tree.permit_expiry": "Permit window",
  "tree.holds_stay_permit": "Stay permit",
  "tree.current_status_code": "Current status",
  "tree.stay_permit_code": "Permit code",
  "tree.renewal_paid": "Renewal payment",
  "tree.overstay_days": "Active overstay",
  "tree.wants_onshore_conversion": "Conversion intent",
  "tree.application_channel": "Application channel",
  "tree.nationalities": "Passports",
  "tree.birth_date": "Age check",
  "tree.category": "Category",
  "tree.trip_scope": "Trip purpose",
  "tree.entry_pattern": "Entry pattern",
  "tree.sponsor_category": "Sponsor category",
  "tree.business_activity": "Business activity",
  "tree.business_sponsor_confirmed": "Company sponsor",
  "tree.work_payer": "Who pays you",
  "tree.work_indonesia_compensation": "Payment source",
  "tree.work_sponsor_confirmed": "Work sponsor",
  "tree.sponsor_government_invitation": "Government invitation",
  "tree.sponsor_government_collaboration": "Government collaboration",
  "tree.sponsor_world_figure_invitation": "World-figure invitation",
  "tree.sponsor_diplomatic_household": "Diplomatic household",
  "tree.sponsor_trade_office": "Trade office sponsor",
  "tree.remote_clients": "Where clients sit",
  "tree.remote_compensation": "Payment source",
  "tree.remote_employer_country": "Employer country",
  "tree.remote_pt_pma": "PT PMA link",
  "tree.stay_days": "Length of stay",
  "tree.investment_vehicle": "Investment basis",
  "tree.investment_pt_pma": "PT PMA commitment",
  "tree.investment_capital_idr": "Investment capital",
  "tree.investment_paid_up_capital_idr": "Paid-up capital",
  "tree.investment_role": "Company role",
  "tree.investment_establishes_company": "Company in Indonesia",
  "tree.investment_foreign_branch": "Foreign branch or subsidiary",
  "tree.investment_ikn_subsidiary": "Subsidiary in IKN",
  "tree.investment_capital_market_only": "Capital market only",
  "tree.investment_meets_threshold": "Published minimum",
  "tree.family_relation": "Family relationship",
  "tree.marital_status": "Marital status",
  "tree.family_sponsor_nationalities": "Sponsor passports",
  "tree.family_sponsor_status_code": "Sponsor status",
  "tree.family_sponsor_permit_basis": "Sponsor permit basis",
  "tree.family_marriage_registered": "Marriage record",
  "tree.family_stepchild_marriage_certificate_confirmed":
    "Parents' marriage certificate",
  "tree.family_stepchild_birth_certificate_confirmed": "Birth certificate",
  "tree.family_sponsor_confirmed": "Family sponsor",
  "tree.retirement_penjamin_confirmed": "Retirement penjamin",
  "tree.retirement_basis": "Long-stay basis",
  "tree.secondhome_basis": "Second Home basis",
  "tree.secondhome_deposit_usd": "Bank deposit",
  "tree.secondhome_state_bank": "Bank type",
  "tree.secondhome_own_name": "Account holder",
  "tree.secondhome_property_value_usd": "Property value",
  "tree.secondhome_passive_income_usd": "Passive income",
  "tree.study_level": "Study level",
  "tree.study_admission_confirmed": "Admission",
  "tree.study_sponsor_confirmed": "Study sponsor",
  "tree.diaspora_connection": "Diaspora context",
  "tree.diaspora_documents": "Connection evidence",
  "tree.other_purpose": "Activity context",
  "tree.other_paid_activity": "Paid activity",
  "tree.review_gate": "Safety check",
  "tree.confirmation": "Your answers",
  "tree.verdict": "Verdict",
  "tree.sr_path_label": "Your path so far",
  "tree.sr_status.done": "answered",
  "tree.sr_status.current": "current step",
  "tree.sr_status.pending": "not yet reached",
  "tree.sr_status.pruned": "different interview branch",

  "process.label": "Where you are in this process",
  "process.step_of": "{{current}} of {{total}} answered",
  "process.phases_label": "Stages",
  "process.phase.location": "Where you are",
  "process.phase.identity": "Who you are",
  "process.phase.intent": "What you came for",
  "process.phase.details": "The details of that purpose",
  "process.phase.review": "Safety check and your answers",
  "process.phase.outcome": "Your result",
  "process.phase_status.done": "complete",
  "process.phase_status.current": "open now",
  "process.phase_status.partial": "in progress",
  "process.phase_status.pending": "not started",
  "process.phase_status.pruned": "not on this branch",
  "process.decides_title": "What this question decides",
  "process.decides_fact":
    "Your answer sets {{plural:this detail|these details}}, which we use:",
  "process.decides_review":
    "Your answer is a safety signal: it can send this case to a Bali Zero consultant, and it is never read as eligibility.",
  "process.decides_context":
    "This question does not set a detail on its own. It steers what you are asked next, and can still count toward something we work out from your answers together.",
  "process.decides_none":
    "No question is open. We have the answers you confirmed.",
  "process.decides_awaiting":
    "No question is open. Your answers are confirmed; your result is not on screen yet.",
  "process.decides_framing":
    "Nothing is answered yet. Every question says what its answer decides before you answer it.",
  "process.decides_confirmation":
    "No question is open. Confirming these answers is what checks your case — and checks it again if you have already been here.",
  "process.categories_title": "Purpose branches",
  "process.category_status.current": "open — being asked now",
  "process.category_status.done": "answered",
  "process.category_status.pruned": "closed",
  "process.category_status.pending": "still open",
  "process.pruned_because":
    "{{count}} {{plural:branch|branches}} closed when you chose “{{category}}”. Nothing you answer inside it can reopen them — go back to the purpose question to change branch.",
  "process.pruned_none":
    "Every purpose branch is still open. Choosing one closes the others.",
  "process.candidates_title": "Options we found for you",
  "process.candidates_pending":
    "No option is named yet. We only check your case after you confirm your answers — this tool never decides eligibility on its own.",
  "process.candidates_none":
    "We found no option for these answers. The result below explains why.",
  "process.candidates_undecided":
    "We could not name an option for these answers. The result below explains why.",
  "process.candidates_follow_up":
    "We have your answers and need one more detail before we can decide. This question asks for it.",
  "process.outcome_node":
    "You are at the last node of this tree: the outcome below is that node, not a separate page.",
  "process.jump_title": "Jump back to an answer",
  "process.jump_aria": "Jump back to {{question}} — you answered {{answer}}",
  "process.jump_empty": "No answer to jump back to yet.",
  "process.answer_unsure": "Not sure",
  "process.announce_prune":
    "You chose {{category}}. {{count}} of the other purpose {{plural:branch|branches}} closed.",

  "paths.counter.label": "{{count}} interview {{plural:branch|branches}}",
  "paths.counter.aria":
    "{{count}} interview {{plural:branch|branches}} remaining",

  "confirmation.title": "Here’s what you told us",
  "confirmation.your_answers": "Your answers",
  "confirmation.group.location": "Current situation",
  "confirmation.group.identity": "About you",
  "confirmation.group.intent": "Your intent",
  "confirmation.group.details": "Branch details",
  "confirmation.group.review": "Review signals",
  "confirmation.assumptions_title": "Assumptions we made",
  "confirmation.edit": "Edit",
  "confirmation.paths_remaining":
    "{{count}} interview {{plural:branch|branches}} remaining",
  "confirmation.price_preview":
    "If a supported Bali Zero service has verified pricing, it will appear as one all-inclusive amount.",
  "confirmation.cta": "See my options",

  // ENDING-ROUND E1: friendly ending surface, same canonical meaning — the
  // engineering-wall copy ("Supported paths found" / "The deterministic
  // engine supports…") moved to `outcome.why_fits`/`outcome.why_supported`
  // where it still belongs; the hero headline now reads as a person talking.
  "verdict.headline.SUPPORTED_CANDIDATES": "A path forward.",
  "verdict.headline.HUMAN_REVIEW_REQUIRED":
    "This needs a human, not an algorithm",
  "verdict.headline.NO_SUPPORTED_PATH":
    "This exact path isn’t supported — here’s what instead",
  // ENDING-ROUND E2: truthful in-page language — the previous "saved"
  // wording overclaimed persistence; only the current page still holds the
  // answers.
  "verdict.headline.TEMPORARILY_UNAVAILABLE": "A pause in the journey.",
  "verdict.headline.NEEDS_INPUT": "A little more to go",
  // D23 "OPTION B-STUDIO": not a real `OutcomeState` — an override VerdictReveal
  // selects instead of `verdict.headline.HUMAN_REVIEW_REQUIRED` when the
  // Studio code is the ONLY review reason. Must never say a person/consultant
  // reviews or checks anything, and must never state a figure the visitor
  // did not declare — the specific numbers already live in the reason's own
  // copy (`SECOND_HOME_BELOW_THRESHOLD_STUDIO`), rendered lower on the page.
  "verdict.headline.SECOND_HOME_STUDIO":
    "Below the Second Home guarantee threshold",
  "verdict.evaluating": "Checking your options…",
  "verdict.eligibility.eligible": "Eligible",
  "verdict.eligibility.likely": "Likely",
  "verdict.eligibility.conditional": "Conditional",
  "verdict.eligibility.likely-not": "Likely not",
  "verdict.state_description.SUPPORTED_CANDIDATES":
    "These options match the answers you gave.",
  "verdict.state_description.HUMAN_REVIEW_REQUIRED":
    "Nothing here is guessed. A Bali Zero advisor reviews cases like yours by hand.",
  "verdict.state_description.NO_SUPPORTED_PATH":
    "We won’t force a fit that isn’t there — here is what your answers do open.",
  "verdict.state_description.TEMPORARILY_UNAVAILABLE":
    "We can’t check your options right now. Your answers are still on this page.",
  "verdict.state_description.NEEDS_INPUT":
    "Finish the interview to see your options.",
  // Must not repeat the Studio sentence that closes the reason's own copy,
  // which renders directly under this description.
  "verdict.state_description.SECOND_HOME_STUDIO":
    "The guarantee figure you declared doesn’t reach the Second Home (E33) thresholds yet. Why, and where to check the other routes, is right below.",
  "verdict.provenance_headline.CLIENT_GUARD":
    "One answer needs clarification first",
  "verdict.provenance_headline.NETWORK_FAILURE":
    "We couldn’t reach the decision service",
  "verdict.provenance_headline.SHADOW": "Assessment verification in progress",
  "verdict.provenance_headline.PREVIEW": "Preview only — not a live decision",
  "verdict.provenance_description.CLIENT_GUARD":
    "No decision was made yet. Review the highlighted answer or continue with a person.",
  "verdict.provenance_description.NETWORK_FAILURE":
    "No result was generated. Your answers were not replaced with a guess.",
  "verdict.provenance_description.SHADOW":
    "Your assessment was recorded for verification; no visa path is shown in this mode.",
  "verdict.provenance_description.PREVIEW":
    "This screen is test data for product review and cannot support a recommendation.",

  "outcome.timeline_title": "Timeline",
  "outcome.timeline_pending":
    "Processing times are set by Ditjen Imigrasi and vary by office and season. Your Bali Zero advisor confirms the calendar for your case before you book travel.",
  "outcome.path_counter": "Path {{index}} of {{total}}",
  "outcome.checked_on": "Checked on {{date}} against the sources above.",
  "outcome.checked_on_plain": "Checked on {{date}}.",
  "outcome.price_label": "All-inclusive price",
  "outcome.price_all_inclusive":
    "Government fees and Bali Zero service included.",
  "outcome.price_valid_until": "Quote valid until {{date}}",
  // Finding #17 (adversarial review 2026-07-17): "Free"/WhatsApp summary
  // header were hardcoded English/Indonesian ternaries in OutcomeSheet.tsx
  // instead of dict entries — invisible to the i18n parity test and to
  // anyone editing copy without reading the component source.
  "outcome.price_free": "Free",
  "outcome.whatsapp_summary_header": "Visa Oracle decision summary:",
  "outcome.checklist_title": "Documents you’ll want ready",
  "outcome.next_steps_title": "What to do next",
  "outcome.whatsapp_cta": "Continue on WhatsApp",
  "outcome.qr_aria":
    "QR code — scan to continue this summary on WhatsApp on your phone",
  "outcome.print_cta": "Print / save as PDF",
  "outcome.copy_cta": "Copy summary",
  "outcome.copy_confirmed": "Copied to clipboard",
  "outcome.copy_failed": "Couldn't copy — try selecting the text manually",
  "outcome.share_title": "Visa Oracle decision summary",
  "outcome.share_cta": "Share summary",
  "outcome.share_confirmed": "Shared",
  "outcome.decision_reference": "Decision reference: {{id}}",
  "outcome.supported_paths": "Supported paths",
  "outcome.rank": "Rank {{rank}}",
  "outcome.axis.legal": "Legal eligibility",
  "outcome.axis.operational": "Current availability",
  "outcome.axis.service": "Bali Zero service",
  "outcome.status.SUPPORTED": "Supported",
  "outcome.status.CONDITIONAL": "Conditional",
  "outcome.status.NOT_SUPPORTED": "Not supported",
  "outcome.status.UNKNOWN": "Unknown",
  "outcome.status.AVAILABLE": "Available",
  "outcome.status.TEMPORARILY_UNAVAILABLE": "Temporarily unavailable",
  "outcome.status.CONTACT_REQUIRED": "Contact required",
  "outcome.status.NOT_OFFERED": "Not offered",
  "outcome.why_supported": "Why this path is supported",
  "outcome.timeline_dates": "{{from}} to {{to}}",
  "outcome.timeline_basis": "Calculated from the assessment date: {{date}}",
  "outcome.document_status.CONDITIONAL": "Conditional",
  "outcome.document_status.UNKNOWN": "To be confirmed",
  // ENDING-ROUND E3: "abstained" is engine jargon.
  "outcome.needs_input_body": "A few details are still missing:",
  "outcome.answer_missing_input": "Answer this",
  "outcome.retryable": "You can safely try this evaluation again.",
  "outcome.not_retryable":
    "A Bali Zero advisor needs to look at this before you continue.",
  "outcome.sources_title": "Sources used for this decision",
  "outcome.source_dates":
    "In force since {{effective}} · last checked {{observed}}",
  "outcome.freshness.CURRENT": "Current",
  "outcome.freshness.STALE": "Being re-checked by our team",
  "outcome.freshness.UNKNOWN": "Last check date unknown",
  "outcome.provenance.CLIENT_GUARD.title": "A person will review this",
  "outcome.provenance.CLIENT_GUARD.body":
    "Your answers need a person’s review before a path can be shown.",
  "outcome.provenance.NETWORK_FAILURE.title": "Decision service unavailable",
  "outcome.provenance.NETWORK_FAILURE.body":
    "We couldn’t reach the decision service. Nothing was guessed — please try again in a few minutes.",
  "outcome.provenance.SHADOW.title": "Verification mode",
  "outcome.provenance.SHADOW.body":
    "This assessment was recorded for verification; no visa path is shown in this mode.",
  "outcome.provenance.PREVIEW.title": "Preview data",
  "outcome.provenance.PREVIEW.body":
    "This content exists only for testing and is not a recommendation.",
  // ENDING-ROUND E8: "Assumptions & caveats, dated" read as a provenance
  // stamp; the dates themselves move to `.oracle-print-only`.
  "outcome.assumptions_receipt_title": "What we assumed",
  "outcome.assumptions_receipt_empty":
    "No assumptions were needed — every answer was given directly.",
  "outcome.freshness_stamp": "Checked against the rules on {{date}}",
  "outcome.disclaimer.not_government":
    "This is a private decision-support tool, not a government service.",
  "outcome.disclaimer.based_on_facts":
    "The result reflects only the facts you entered and the dated sources shown above.",
  "outcome.disclaimer.not_approval":
    "It is not an approval, a guarantee, or a filing.",
  "outcome.disclaimer.complex_to_human":
    "If you disclosed a criminal record, or gave an answer these rules cannot assess, a Bali Zero advisor reviews your case before any path is confirmed. Any other disclosure appears on your result as a condition we check with you before filing. The decision is always Ditjen Imigrasi’s, never this tool’s.",
  // D23 "OPTION B-STUDIO": replaces `outcome.disclaimer.complex_to_human` on
  // a Studio-only hold, which is never a human/consultant hold.
  "outcome.disclaimer.second_home_studio":
    "This result is about a declared guarantee figure below the Second Home (E33) thresholds — the Second Home Studio shows the routes and the numbers for your case.",
  "outcome.alternatives_title": "The door that is open",
  "outcome.alternatives_intro": "Another route this tool can confirm for you.",
  "outcome.no_path_body":
    "The combination you described does not match any visa path this tool can confirm.",
  "outcome.temporarily_unavailable_body":
    "We can’t run the check right now. Please try again in a few minutes.",
  "outcome.human_review_body":
    "Your case needs a Bali Zero advisor’s review — nothing was guessed on your behalf.",
  // Slice A2 (PLAN VISA-ORACLE-DW-20260919 §1.6): `notices[]` rendered next
  // to whatever verdict is already shown, on every state that can carry one.
  // ENDING-ROUND E9: no test pins the old title text (verified 2026-09-27).
  "outcome.conditions.title": "Before you apply",
  // S1 (GATE-A2-REPORT-6849 MEDIUM-2): the prior wording ("do not change
  // the result above") read as a reassurance that the disclosed matter has
  // no bearing on the outcome — false for a PEP/sanctions or source-of-funds
  // condition, whose submission-time check absolutely can change it. State
  // the engine fact only: a condition attached, checked with the visitor.
  "outcome.conditions.intro":
    "The result above was reached with these conditions attached. Our team checks each one with you before submission.",
  "outcome.review_group_case.title":
    "What a Bali Zero advisor will check about your case",
  "outcome.review_group_system.title":
    "Checks on our side, not on your answers",
  "outcome.review.element.rule": "Why this is paused",
  "outcome.review.element.checked": "What the reviewer checks",
  "outcome.review.element.prepare": "What to prepare",
  "outcome.review.element.handling": "How this is handled",
  "outcome.review_cause_unsure": "You answered “Not sure” to: {{question}}",
  "outcome.review_cause_answer": "You answered “{{answer}}” to: {{question}}",
  "outcome.review_cause_edit_aria": "Edit your answer to: {{question}}",
  "outcome.overstay_reassurance":
    "Overstay is fixable. It is not the end of your story here.",
  // D23 "OPTION B-STUDIO" (2026-09-16): this ONE review code is never
  // introduced with "needs a person's judgment" (`outcome.human_review_
  // body`) — it routes to a self-serve calculator, not a person.
  "outcome.second_home_studio_link": "Open the Second Home Studio",

  "prototype.badge": "Visa decision support",
  "prototype.badge.detail":
    "Only paths this tool can confirm appear as supported.",

  "theme.toggle.aria": "Switch between light and dark",
  "theme.toggle.light": "Light",
  "theme.toggle.dark": "Dark",
  "language.toggle.aria": "Switch language",
  "language.option.en": "EN",
  "language.option.id": "ID",
  "language.option.en.aria": "Switch to English",
  "language.option.id.aria": "Switch to Bahasa Indonesia",

  "footer.disclaimer":
    "Visa Oracle is private decision support. It is not a government service, approval, or filing — Ditjen Imigrasi decides. Unknown or complex cases go to human review.",
  "footer.privacy": "Visa Oracle privacy policy",
  "process.branch_preview_more":
    "and {{count}} more {{plural:question|questions}}",
  "process.branch_reopen_aria":
    "Switch to {{category}} — reopens this branch and asks its questions",
  "tree.investment_currency": "Investment currency",
  "tree.investment_amount_usd": "Investment amount",
  "tree.retirement_undecided_basis": "Long-stay route",

  // ENDING-ROUND additive keys (E4/E5/E7): presentation-only friendly
  // ending copy, same canonical meaning as the jargon they replace.
  "outcome.why_fits": "Why this fits",
  "outcome.reason_generic":
    "The assessment supports this option for the answers you provided.",
  "outcome.legal_references": "Legal references",
  // E5 extension: found via a live NO_SUPPORTED_PATH screenshot showing
  // "Verified reason: NO_SUPPORTED_PATH" — `noPathReasons` shares the same
  // raw-code fallback as a candidate's support reasons, but "the assessment
  // supports this option" would be false inside a NOT-supported result.
  "outcome.reason_generic_no_path":
    "This path isn't supported for the answers you provided.",
} as const;

type Keys = keyof typeof en;

const id: Record<Keys, string> = {
  "framing.title": "Peta, bukan permohonan",
  "framing.body":
    "Jawab dengan jujur, termasuk “Saya tidak tahu.” Tidak ada yang diajukan di sini, dan alat ini tidak pernah memilih visa untuk Anda.",
  "framing.cta": "Mulai",

  "q.in_indonesia": "Apakah Anda sedang berada di Indonesia sekarang?",
  "q.in_indonesia.hint":
    "Ini menentukan pertanyaan mana yang relevan selanjutnya.",
  "q.in_indonesia.opt.yes": "Ya, saya di sini",
  "q.in_indonesia.opt.no": "Belum, saya sedang merencanakan",
  "why.in_indonesia":
    "Lokasi Anda saat ini menentukan apakah kami melihat izin yang bisa diurus di dalam Indonesia atau visa yang diajukan sebelum berangkat.",

  "q.permit_expiry": "Kapan izin tinggal Anda saat ini berakhir?",
  "q.permit_expiry.hint":
    "Tanggal pada visa atau ITAS/KITAS Anda — bukan paspor.",
  "q.permit_expiry.label": "Tanggal berakhir",
  "why.permit_expiry":
    "Kami memerlukan tanggalnya untuk menilai sisa waktu Anda. Tanggal ini tidak dipakai untuk memilihkan jalur pengajuan.",
  "q.current_status_code":
    "Kode apa yang tercantum pada izin tinggal Anda saat ini?",
  "q.current_status_code.hint":
    "Masukkan kode yang tercetak persis. Pilih Tidak yakin daripada menerjemahkan nama izin.",
  "q.current_status_code.label": "Kode izin saat ini",
  "q.current_status_code.opt.A1": "A1",
  "q.current_status_code.opt.C1": "C1",
  "q.current_status_code.opt.C2": "C2",
  "q.current_status_code.opt.C6": "C6",
  "q.current_status_code.opt.ITK_FROM_BVK": "ITK hasil konversi dari BVK",
  "q.current_status_code.opt.ITK_FROM_VISIT_C":
    "ITK hasil konversi dari Kunjungan C",
  "q.current_status_code.opt.ITK_FROM_VISIT_D":
    "ITK hasil konversi dari Kunjungan D",
  "q.current_status_code.opt.ITK_PERALIHAN": "ITK Peralihan",
  "q.current_status_code.opt.other": "Kode lain — perlu tinjauan manusia",
  "why.current_status_code":
    "Kami memakai kode persis seperti yang tercetak pada izin Anda. Kode ini tidak pernah ditebak dari nama izin.",
  "q.holds_stay_permit":
    "Apakah Anda saat ini memegang izin tinggal terbatas atau tetap (KITAS / KITAP)?",
  "why.holds_stay_permit":
    "Katalog kode-E hanya berlaku untuk pemegang KITAS/KITAP; yang lain menjawab daftar kode yang lebih pendek di bawah.",
  "q.stay_permit_code": "Kode apa yang tercantum pada izin Anda?",
  "q.stay_permit_code.hint":
    "Masukkan kode persis dari kartu Anda. Pilih Tidak yakin daripada menebak.",
  "q.stay_permit_code.opt.E23": "E23 — Visa Kerja",
  "q.stay_permit_code.opt.E23U":
    "E23U — Visa Kerja Asisten Rumah Tangga Diplomat Asing",
  "q.stay_permit_code.opt.E23V": "E23V — Visa Kerja Kantor Dagang dan Ekonomi",
  "q.stay_permit_code.opt.E28A": "E28A — Visa Investor",
  "q.stay_permit_code.opt.E28B": "E28B — Visa Investor Pendirian Perusahaan",
  "q.stay_permit_code.opt.E28C":
    "E28C — Visa Investor Tanpa Mendirikan Perusahaan",
  "q.stay_permit_code.opt.E28D":
    "E28D — Visa Investor Pendirian Kantor Cabang atau Anak Perusahaan",
  "q.stay_permit_code.opt.E28F":
    "E28F — Visa Investor Anak Perusahaan Ibukota Nusantara",
  "q.stay_permit_code.opt.E30": "E30 — Visa Pendidikan",
  "q.stay_permit_code.opt.E30A": "E30A — Visa Pendidikan Dasar dan Menengah",
  "q.stay_permit_code.opt.E30B": "E30B — Visa Pendidikan Tinggi",
  "q.stay_permit_code.opt.E30E":
    "E30E — Visa Pendidikan Kawasan Ekonomi Khusus",
  "q.stay_permit_code.opt.E30F": "E30F — Visa Pertukaran Pelajar",
  "q.stay_permit_code.opt.E31A": "E31A — Visa Keluarga Suami/Istri WNI",
  "q.stay_permit_code.opt.E31B":
    "E31B — Visa Keluarga Suami/Istri Pemegang ITAS/ITAP",
  "q.stay_permit_code.opt.E31C":
    "E31C — Visa Keluarga Anak Hasil Perkawinan Sah WNA-WNI",
  "q.stay_permit_code.opt.E31D":
    "E31D — Visa Keluarga Anak Bawaan WNA Perkawinan Sah WNA-WNI",
  "q.stay_permit_code.opt.E31E": "E31E — Visa Keluarga Anak Pemegang ITAS/ITAP",
  "q.stay_permit_code.opt.E31F":
    "E31F — Visa Keluarga Anak dengan Orang Tua WNI",
  "q.stay_permit_code.opt.E31G": "E31G — Visa Keluarga Orang Tua dari Anak WNI",
  "q.stay_permit_code.opt.E31H":
    "E31H — Visa Keluarga Orang Tua dari Anak Pemegang ITAS/ITAP",
  "q.stay_permit_code.opt.E31J":
    "E31J — Visa Keluarga Anak yang Bergabung dengan Saudara Kandung Pemegang ITAS/ITAP",
  "q.stay_permit_code.opt.E33": "E33 — Visa Rumah Kedua",
  "q.stay_permit_code.opt.E33A":
    "E33A — Visa Rumah Kedua Tenaga Ahli Undangan Pemerintah",
  "q.stay_permit_code.opt.E33B":
    "E33B — Visa Rumah Kedua Kolaborasi Keahlian Khusus",
  "q.stay_permit_code.opt.E33C":
    "E33C — Visa Rumah Kedua Tokoh Dunia Undangan Pemerintah",
  "q.stay_permit_code.opt.E33E":
    "E33E — Visa Rumah Kedua Lansia untuk 5 Tahun Golden Visa",
  "q.stay_permit_code.opt.E33F": "E33F — Visa Rumah Kedua Lansia untuk 1 Tahun",
  "q.stay_permit_code.opt.E33G": "E33G — Visa Rumah Kedua Pekerja Jarak Jauh",
  "why.stay_permit_code":
    "Kami memakai kode persis seperti yang tercetak, sama seperti pada daftar kode di atas. Kode ini tidak pernah ditebak dari nama izin.",

  "q.renewal_paid": "Apakah Anda sudah membayar perpanjangan izin tinggal ini?",
  "q.renewal_paid.hint":
    "Jawab soal pembayaran, bukan berkas — ini terpisah dari apakah perpanjangan sudah diserahkan.",
  "why.renewal_paid":
    "Perpanjangan dianggap telah diserahkan begitu pembayaran dilakukan, bukan begitu dokumen diserahkan — pemegang izin yang sedang dalam proses perpanjangan tetap berada pada izin yang mereka perpanjang, sama seperti pemegang izin aktif lainnya.",

  "q.overstay_days": "Berapa hari overstay yang aktif saat ini?",
  "q.overstay_days.hint":
    "Masukkan 0 jika tidak ada overstay aktif. Jangan masukkan riwayat overstay lama di sini.",
  "q.overstay_days.label": "Overstay saat ini",
  "why.overstay_days":
    "Jumlah hari overstay ditanyakan tersendiri karena sangat memengaruhi pilihan yang tersedia. Jumlah ini tidak pernah dihitung dari tanggal berakhir.",
  "q.wants_onshore_conversion":
    "Apakah Anda ingin mengubah status tanpa meninggalkan Indonesia?",
  "q.wants_onshore_conversion.hint":
    "Jawab tentang proses yang Anda inginkan, bukan apakah proses itu akan disetujui.",
  "q.wants_onshore_conversion.offshore":
    "Setelah berada di Indonesia, apakah Anda berencana beralih ke izin lain tanpa meninggalkan Indonesia?",
  "q.wants_onshore_conversion.offshore.hint":
    "Jawab tentang proses yang Anda rencanakan setelah tiba, bukan apakah proses itu akan disetujui.",
  "why.wants_onshore_conversion":
    "Jawaban ya atau tidak Anda hanya menunjukkan proses mana yang Anda maksud. Jawaban ini tidak memilihkan jalur konversi.",
  "q.application_channel":
    "Kanal permohonan mana yang benar-benar Anda jalani?",
  "q.application_channel.hint":
    "Pilih hanya kanal yang sudah dikonfirmasi untuk kasus Anda, atau pilih Tidak yakin.",
  "q.application_channel.opt.OFFSHORE":
    "Mengajukan setelah meninggalkan Indonesia",
  "q.application_channel.opt.ONSHORE_CONVERSION": "Konversi status onshore",
  "q.application_channel.opt.STATUS_BRIDGING": "Proses status bridging",
  "why.application_channel":
    "Kami memakai kanal yang Anda pilih apa adanya. Kanal tidak pernah ditetapkan dari tanggal Anda.",
  "q.application_channel.conflict":
    "Kanal ini tidak sesuai dengan jawaban Anda sebelumnya tentang mengubah status tanpa meninggalkan Indonesia. Kembali dan perbaiki salah satu dari kedua jawaban — kami tidak akan menebak mana yang benar.",

  "q.nationalities": "Kewarganegaraan apa yang tercantum di paspor Anda?",
  "q.nationalities.hint":
    "Pilih setiap negara paspor. Jawaban tersimpan tetap berupa kode negara yang tidak bergantung pada bahasa.",
  "q.nationalities.label": "Negara paspor",
  "why.nationalities":
    "Kewarganegaraan diperiksa persis seperti yang Anda berikan. Beberapa kewarganegaraan tetap dipisahkan dan tidak pernah ditebak.",
  "q.birth_date": "Kapan tanggal lahir Anda?",
  "q.birth_date.hint":
    "Beberapa visa punya syarat usia; tanggal lahir Anda hanya dipakai untuk memeriksanya.",
  "q.birth_date.label": "Tanggal lahir",
  "why.birth_date":
    "Beberapa visa membedakan orang dewasa dan anak. Usia Anda saja tidak pernah menentukan kelayakan.",
  "q.guardian_consent":
    "Apakah orang tua atau wali sah mengisi ini bersama Anda?",
  "q.guardian_consent.help":
    "Kami menanyakan ini karena pemohon berusia di bawah 18 tahun. Kami hanya mencatat jawaban Anda atas pertanyaan ini — tanpa nama, tanpa dokumen, tanpa data kontak.",
  "why.guardian_consent":
    "Pemohon di bawah 18 tahun tidak dapat memberikan persetujuan ini sendiri, sehingga Bali Zero meminta orang dewasa memastikan kehadirannya sebelum penilaian dilanjutkan.",

  "lane.expired.notice":
    "Izin tinggal Anda sudah berakhir. Overstay bisa diselesaikan. Ini bukan akhir cerita Anda di sini — kasus ini selalu ditangani manusia, dan kami tidak akan menampilkan angka yang menakutkan di layar ini.",
  "lane.urgent.notice":
    "Waktu Anda tinggal 1–2 hari. Ini terlalu mepet untuk pemeriksaan otomatis — konsultan Bali Zero perlu melihat kasus ini hari ini.",
  "lane.bridging.notice":
    "Tanggal yang Anda masukkan tinggal tujuh hari atau kurang. Kasus Anda dapat diteruskan ke konsultan Bali Zero untuk ditinjau, dan alat ini tidak memilihkan jalur bridging atau konversi untuk Anda.",
  "lane.extend.notice":
    "Anda masih punya waktu untuk membandingkan Extend dan Convert.",
  "lane.planning.notice":
    "Waktu masih longgar — ini perencanaan, bukan hal mendesak.",

  "q.category": "Apa tujuan Anda ke Indonesia?",
  "q.category.hint":
    "Pilih yang paling mendekati — bisa diperjelas berikutnya.",
  "why.category":
    "Arah yang Anda pilih hanya menentukan pertanyaan berikutnya. Arah ini tidak menentukan apakah jalur visa tersedia — jawaban Anda yang menentukan.",
  "q.category.opt.tourism": "Wisata & kunjungan singkat",
  "q.category.opt.business": "Bisnis (tanpa bekerja)",
  "q.category.opt.work": "Kerja & ketenagakerjaan",
  "q.category.opt.invest": "Investasi & golden visa",
  "q.category.opt.remote": "Pekerja remote",
  "q.category.opt.family": "Keluarga & pernikahan",
  "q.category.opt.retirement": "Pensiun",
  "q.category.opt.second_home": "Second Home",
  "q.category.opt.study": "Studi",
  "q.category.opt.diaspora": "Diaspora & eks-WNI",
  "q.category.opt.other": "Lainnya",

  "q.boolean.yes": "Ya",
  "q.boolean.no": "Tidak",
  "q.boolean.not_applicable": "Tidak berlaku",
  "q.trip_scope": "Apakah ini satu-satunya tujuan perjalanan Anda?",
  "q.trip_scope.hint":
    "Pilih beberapa jika kerja, keluarga, studi, bisnis, atau tujuan lain saling tumpang tindih.",
  "q.trip_scope.opt.single": "Ya — satu tujuan utama",
  "q.trip_scope.opt.multiple": "Tidak — dua tujuan atau lebih tumpang tindih",
  "why.trip_scope":
    "Tujuan yang tumpang tindih memerlukan penilaian konsultan, jadi jawaban ini tidak dipakai untuk memutuskan apa pun secara otomatis.",
  "q.entry_pattern": "Bagaimana Anda berencana masuk ke Indonesia?",
  "q.entry_pattern.hint": "Pilih pola yang benar-benar Anda rencanakan.",
  "q.entry_pattern.opt.SINGLE": "Satu kali masuk",
  "q.entry_pattern.opt.MULTIPLE": "Lebih dari satu kali masuk",
  "why.entry_pattern":
    "Pilihan masuk satu kali atau berkali-kali kami pakai persis seperti yang Anda pilih.",

  "q.sponsor_category":
    "Siapa yang mensponsori masa tinggal Anda di Indonesia?",
  "q.sponsor_category.hint":
    "Pilih pihak yang menyediakan atau menjamin izin Anda, bukan yang membiayai kebutuhan sehari-hari Anda.",
  "q.sponsor_category.opt.NONE":
    "Tidak ada sponsor — saya memenuhi syarat sendiri",
  "q.sponsor_category.opt.INDIVIDUAL":
    "Perorangan (sponsor keluarga atau pribadi)",
  "q.sponsor_category.opt.EMPLOYER": "Pemberi kerja — perusahaan di Indonesia",
  "q.sponsor_category.opt.EDUCATION": "Institusi pendidikan",
  "q.sponsor_category.opt.INVESTMENT": "Investasi atau perusahaan milik saya",
  "q.sponsor_category.opt.GOVERNMENT": "Instansi pemerintah",
  "why.sponsor_category":
    "Kami mencatat jenis sponsor Anda. Belum ada aturan saat ini yang memakainya; ini hanya menyiapkan data untuk aturan yang akan datang.",

  "q.sponsor_government_invitation":
    "Apakah Anda memiliki undangan tertulis dari instansi pemerintah pusat Indonesia yang diberikan kepada Anda sebagai tenaga ahli?",
  "q.sponsor_government_invitation.hint":
    "Jawab tidak jika undangan belum tertulis, atau tidak berasal dari instansi pemerintah pusat Indonesia.",
  "why.sponsor_government_invitation":
    "Hanya jawaban ya atau tidak Anda tentang undangan pemerintah yang dipakai di sini.",
  "q.sponsor_government_collaboration":
    "Apakah Anda memiliki komitmen kolaborasi yang terkonfirmasi dengan instansi atau lembaga pemerintah Indonesia, berdasarkan keahlian khusus Anda?",
  "q.sponsor_government_collaboration.hint":
    "Diskusi atau usulan yang belum dikonfirmasi dihitung sebagai tidak.",
  "why.sponsor_government_collaboration":
    "Hanya jawaban ya atau tidak Anda tentang kolaborasi pemerintah yang terkonfirmasi yang dipakai di sini.",
  "q.sponsor_world_figure_invitation":
    "Apakah instansi pemerintah Indonesia mengundang Anda sebagai tokoh dunia — seseorang dengan reputasi internasional?",
  "q.sponsor_world_figure_invitation.hint":
    "Jawab ya hanya jika instansi pemerintah telah mengundang Anda dalam kapasitas tersebut.",
  "why.sponsor_world_figure_invitation":
    "Hanya jawaban ya atau tidak Anda tentang undangan sebagai tokoh dunia yang dipakai di sini.",
  "q.sponsor_diplomatic_household":
    "Apakah posisi ini berada di rumah tangga diplomat asing yang bertugas di Indonesia?",
  "q.sponsor_diplomatic_household.hint":
    "Jawab tidak jika Anda akan bekerja untuk pihak selain rumah tangga diplomat tersebut.",
  "why.sponsor_diplomatic_household":
    "Hanya jawaban ya atau tidak Anda tentang posisi di rumah tangga diplomat yang dipakai di sini.",
  "q.sponsor_trade_office":
    "Apakah penjamin Anda adalah kantor perwakilan dagang atau ekonomi asing di Indonesia?",
  "q.sponsor_trade_office.hint":
    "Jawab tidak jika penjamin Anda adalah jenis organisasi lain.",
  "why.sponsor_trade_office":
    "Hanya jawaban ya atau tidak Anda tentang penjamin berupa kantor perwakilan dagang yang dipakai di sini.",
  "q.business_activity": "Apa kegiatan utama Anda dalam perjalanan bisnis?",
  "q.business_activity.hint":
    "Jelaskan kegiatannya, bukan nama visa. Rapat, negosiasi, konferensi, dan penjajakan investasi dapat dinilai di sini; pelatihan atau kegiatan lain diteruskan ke konsultan Bali Zero untuk ditinjau.",
  "q.business_activity.opt.meetings": "Rapat atau kunjungan lokasi",
  "q.business_activity.opt.negotiation": "Negosiasi atau penandatanganan",
  "q.business_activity.opt.conference": "Konferensi atau pameran dagang",
  "q.business_activity.opt.exploring":
    "Menjajaki peluang berinvestasi atau membuka usaha di sini",
  "q.business_activity.opt.training": "Memberi atau menerima pelatihan",
  "q.business_activity.opt.other": "Kegiatan bisnis lainnya",
  "why.business_activity":
    "Menjajaki peluang berinvestasi atau membuka usaha diperlakukan sebagai tujuan investasi, lalu kami menanyakan beberapa pertanyaan yang menentukannya. Jawaban lain di sini hanya menentukan apakah konsultan Bali Zero perlu meninjau perjalanan Anda: pelatihan dan “kegiatan bisnis lainnya” perlu, jawaban lainnya tidak.",
  "q.business_sponsor_confirmed":
    "Apakah sponsor perusahaan atau penjamin sudah mengonfirmasi dukungan proses?",
  "q.business_sponsor_confirmed.hint":
    "Percakapan atau calon mitra belum berarti sponsor sudah dikonfirmasi.",
  "why.business_sponsor_confirmed":
    "Apakah sponsor Anda sudah mengonfirmasi dicatat sebagai jawaban ya atau tidak tersendiri.",

  "q.work_payer":
    "Apakah perusahaan berbadan hukum Indonesia yang mempekerjakan dan menggaji Anda di sini?",
  "q.work_payer.hint":
    "Bukan “apakah Anda butuh KITAS kerja” — tapi siapa yang benar-benar menggaji Anda.",
  "why.work_payer":
    "Kami hanya memakai apakah pemberi kerja Anda adalah entitas Indonesia. Visa tidak dipilih berdasarkan hal itu.",
  "q.work_payer.opt.yes": "Ya, entitas Indonesia yang menggaji saya",
  "q.work_payer.opt.no": "Tidak, saya digaji dari luar negeri",

  "q.work_indonesia_compensation":
    "Apakah ada kompensasi untuk kegiatan ini yang berasal dari sumber Indonesia?",
  "q.work_indonesia_compensation.hint":
    "Jawab tentang sumber pembayaran, bukan mata uang atau rekening bank.",
  "why.work_indonesia_compensation":
    "Ini menunjukkan dari mana penghasilan Anda berasal. Jumlah dan kelayakan tidak disimpulkan darinya.",
  "q.work_sponsor_confirmed":
    "Apakah sponsor kerja Indonesia sudah mengonfirmasi dukungan proses?",
  "q.work_sponsor_confirmed.hint":
    "Percakapan atau calon pemberi kerja belum berarti sponsor sudah dikonfirmasi.",
  "why.work_sponsor_confirmed":
    "Hanya jawaban ya atau tidak Anda tentang konfirmasi sponsor yang dipakai di sini.",

  "q.remote_clients": "Di mana klien atau pemberi kerja Anda berada?",
  "q.remote_clients.hint":
    "Ini yang membedakan jalur pekerja remote dari jalur kerja biasa.",
  "why.remote_clients":
    "Kami hanya memakai apakah Anda melayani klien Indonesia. Hal ini tidak diasumsikan dari tempat tinggal Anda.",
  "q.remote_clients.opt.foreign":
    "Luar negeri — mereka menggaji saya dari luar Indonesia",
  "q.remote_clients.opt.indonesian":
    "Indonesia — saya secara efektif bekerja di sini",
  "q.remote_clients.opt.mixed": "Campuran keduanya",

  "q.remote_compensation":
    "Apakah ada kompensasi kerja remote yang berasal dari sumber Indonesia?",
  "q.remote_compensation.hint":
    "Pertanyaan ini menanyakan asal pembayaran, bukan jumlah penghasilan.",
  "why.remote_compensation":
    "Jawaban dipetakan langsung ke work.indonesia_source_compensation.",
  "q.remote_employer_country":
    "Di negara mana pemberi kerja atau klien utama Anda terdaftar?",
  "q.remote_employer_country.hint":
    "Masukkan satu kode negara ISO dua huruf, misalnya IT.",
  "q.remote_employer_country.label": "Kode negara pemberi kerja",
  "why.remote_employer_country":
    "Kami memakai kode negara persis seperti yang Anda masukkan dan tidak menafsirkannya.",
  "q.remote_pt_pma":
    "Apakah rencana kerja remote ini terikat pada komitmen PT PMA Indonesia?",
  "q.remote_pt_pma.hint":
    "Pilih ya hanya untuk komitmen nyata, bukan perusahaan yang mungkin dibentuk nanti.",
  "why.remote_pt_pma":
    "Ini dipetakan langsung ke investment.pt_pma_committed dan tidak menyiratkan persetujuan.",

  "q.investment_vehicle": "Apa dasar konkret rencana Anda?",
  "q.investment_vehicle.hint": "Ini hanya menentukan pertanyaan berikutnya.",
  "q.investment_vehicle.opt.pt_pma": "Komitmen PT PMA Indonesia",
  "q.investment_vehicle.opt.property": "Pengaturan properti",
  "q.investment_vehicle.opt.bank_deposit": "Deposito bank atas nama saya",
  "q.investment_vehicle.opt.merit": "Prestasi, talenta, atau kontribusi publik",
  "q.investment_vehicle.opt.family": "Jalur terkait keluarga",
  "q.investment_vehicle.opt.capital_market":
    "Hanya investasi pasar modal, seperti saham tercatat atau obligasi",
  "q.investment_vehicle.opt.undecided": "Saya belum memilih dasar",
  "why.investment_vehicle":
    "Ini hanya menentukan pertanyaan yang kami ajukan berikutnya. Jawaban ini tidak pernah memilih jalur visa.",
  "q.investment_currency":
    "Dalam mata uang apa Anda dapat mengomitmenkan jumlah investasi?",
  "q.investment_currency.hint":
    "Ini hanya menentukan pertanyaan jumlah berikutnya. Tidak ada konversi yang pernah dilakukan antar mata uang.",
  "q.investment_currency.opt.idr": "Rupiah Indonesia (IDR)",
  "q.investment_currency.opt.usd": "Dolar AS (USD)",
  "q.investment_currency.opt.still_unsure": "Saya belum bisa memastikan",
  "why.investment_currency":
    "Ini hanya memilih pertanyaan jumlah mana yang mengikuti. Ini tidak pernah memilih jalur visa, dan tidak ada angka yang dikonversi antar mata uang.",
  "q.investment_pt_pma": "Apakah komitmen PT PMA sudah konkret?",
  "q.investment_pt_pma.hint":
    "Jawab tidak untuk ide, pembicaraan awal, atau rencana tanpa komitmen.",
  "why.investment_pt_pma":
    "Kami hanya mencatat apakah komitmen Anda sudah konkret. Jumlah atau status tidak diasumsikan darinya.",
  "q.investment_capital_idr":
    "Berapa modal investasi yang sudah dikomitmenkan?",
  "q.investment_capital_idr.hint":
    "Masukkan jumlah rupiah bulat yang dapat didukung bukti.",
  "q.investment_capital_idr.label": "Modal investasi yang dikomitmenkan",
  "why.investment_capital_idr":
    "Jumlah dipakai persis seperti yang Anda masukkan. Tidak ada ambang batas yang ditampilkan atau diasumsikan di sini.",
  "q.investment_amount_usd":
    "Berapa jumlah investasi yang dikomitmenkan, dalam dolar AS?",
  "q.investment_amount_usd.hint":
    "Masukkan jumlah dolar utuh yang tepat dan dapat Anda dukung dengan bukti.",
  "q.investment_amount_usd.label": "Jumlah investasi yang dikomitmenkan",
  "why.investment_amount_usd":
    "Jumlah dipakai dalam mata uang yang Anda pilih. Tidak ada ambang batas yang ditampilkan atau diasumsikan di sini, dan tidak ada konversi yang dilakukan.",
  "q.investment_paid_up_capital_idr":
    "Berapa modal disetor yang sudah terdokumentasi?",
  "q.investment_paid_up_capital_idr.hint":
    "Masukkan jumlah rupiah bulat; pilih Tidak yakin daripada memperkirakan.",
  "q.investment_paid_up_capital_idr.label": "Modal disetor terdokumentasi",
  "why.investment_paid_up_capital_idr":
    "Jumlah modal disetor dipisahkan dari modal investasi yang Anda rencanakan.",
  "q.investment_role": "Peran apa yang akan Anda pegang di perusahaan?",
  "q.investment_role.hint": "Pilih deskripsi peran yang tepat.",
  "q.investment_role.opt.SHAREHOLDER_DIRECTOR": "Pemegang saham dan direktur",
  "q.investment_role.opt.SHAREHOLDER_COMMISSIONER":
    "Pemegang saham dan komisaris",
  "q.investment_role.opt.EMPLOYEE": "Karyawan",
  "q.investment_role.opt.NO_OPERATIONAL_ROLE": "Tanpa peran operasional",
  "q.investment_role.opt.OTHER": "Peran lain",
  "why.investment_role":
    "Peran yang Anda pilih dipakai persis seperti pilihan Anda.",
  "q.investment_establishes_company":
    "Apakah Anda akan mendirikan perusahaan di Indonesia sebagai bagian dari investasi ini?",
  "q.investment_establishes_company.hint":
    "Anak perusahaan yang didirikan di Indonesia, termasuk anak perusahaan dari perusahaan di luar negeri, dihitung sebagai perusahaan. Jawab tidak jika investasi ini tidak melibatkan pendirian perusahaan di Indonesia.",
  "why.investment_establishes_company":
    "Hanya jawaban ya atau tidak Anda tentang pendirian perusahaan yang dipakai di sini.",
  "q.investment_foreign_branch":
    "Apakah Anda mendirikan kantor cabang atau anak perusahaan dari perusahaan yang sudah ada di luar Indonesia?",
  "q.investment_foreign_branch.hint":
    "Jawab tidak jika perusahaan tersebut belum ada di luar Indonesia.",
  "why.investment_foreign_branch":
    "Hanya jawaban ya atau tidak Anda tentang kantor cabang atau anak perusahaan dari perusahaan asing yang dipakai di sini.",
  "q.investment_ikn_subsidiary":
    "Apakah perusahaan yang Anda dirikan merupakan anak perusahaan yang berlokasi di Ibu Kota Nusantara (IKN)?",
  "q.investment_ikn_subsidiary.hint":
    "Jawab tidak untuk perusahaan yang berlokasi di tempat lain di Indonesia.",
  "why.investment_ikn_subsidiary":
    "Hanya jawaban ya atau tidak Anda tentang anak perusahaan di IKN yang dipakai di sini.",
  "q.investment_capital_market_only":
    "Apakah investasi Anda hanya ditempatkan pada instrumen pasar modal, tanpa mendirikan perusahaan?",
  "q.investment_capital_market_only.hint":
    "Jawab tidak jika ada bagian investasi di luar pasar modal.",
  "why.investment_capital_market_only":
    "Hanya jawaban ya atau tidak Anda tentang investasi yang hanya di pasar modal yang dipakai di sini.",
  "q.investment_meets_threshold":
    "Apakah investasi Anda memenuhi seluruh batas minimum keuangan yang dipublikasikan untuk jalur yang Anda pilih — jumlah modal, dan omzet tahunan jika jalur tersebut mensyaratkannya?",
  "q.investment_meets_threshold.hint":
    "Jika Anda tidak mengetahui batas minimum yang dipublikasikan untuk jalur Anda, jawab tidak: Oracle tidak pernah menganggapnya terpenuhi.",
  "why.investment_meets_threshold":
    "Hanya jawaban ya atau tidak Anda yang dipakai di sini. Tidak ada jumlah yang ditampilkan atau diasumsikan di sini.",
  "q.unit.idr": "IDR",
  "q.unit.usd": "USD",
  "q.unit.usd_month": "USD per bulan",

  "q.family_relation": "Apa hubungan Anda dengan calon sponsor?",
  "q.family_relation.hint": "Pilih hubungan yang dapat dibuktikan.",
  "q.family_relation.opt.SPOUSE": "Suami atau istri",
  "q.family_relation.opt.CHILD": "Anak",
  "q.family_relation.opt.PARENT": "Orang tua",
  "q.family_relation.opt.SIBLING": "Saudara kandung",
  "q.family_relation.opt.DEPENDENT": "Tanggungan lain",
  "q.family_relation.opt.STEPCHILD": "Anak tiri",
  "q.family_relation.opt.OTHER": "Hubungan lain",
  "why.family_relation":
    "Hubungan yang Anda pilih dipakai persis seperti pilihan Anda.",
  "q.marital_status": "Apa status perkawinan Anda saat ini?",
  "q.marital_status.hint": "Pilih status hukum Anda saat ini.",
  "q.marital_status.opt.SINGLE": "Belum menikah",
  "q.marital_status.opt.MARRIED": "Menikah",
  "q.marital_status.opt.DIVORCED": "Bercerai",
  "q.marital_status.opt.WIDOWED": "Duda atau janda",
  "q.marital_status.opt.OTHER": "Status lain",
  "why.marital_status":
    "Status pernikahan Anda dipakai persis seperti pilihan Anda.",
  "q.family_sponsor_nationalities":
    "Kewarganegaraan apa yang tercantum di paspor sponsor Anda?",
  "q.family_sponsor_nationalities.hint":
    "Pilih setiap negara paspor. Jawaban tetap terpisah dari kewarganegaraan Anda.",
  "q.family_sponsor_nationalities.label": "Negara paspor sponsor",
  "why.family_sponsor_nationalities":
    "Kewarganegaraan sponsor ditanyakan terpisah dan tidak pernah disalin dari paspor Anda.",
  "q.family_sponsor_status_code":
    "Izin tinggal apa yang saat ini dimiliki sponsor Anda?",
  "q.family_sponsor_status_code.hint":
    "Pilih opsi yang tertera di kartu KITAS/KITAP sponsor Anda — ini menanyakan izin sponsor Anda, bukan status Anda sendiri. Pilih “Saya tidak yakin” jika tidak dapat memastikannya.",
  "why.family_sponsor_status_code":
    "Memastikan sponsor Anda sudah memiliki izin tinggal yang memenuhi syarat sebelum kami menyebutkan produk visa keluarga untuk Anda.",
  "q.family_sponsor_permit_basis":
    "Apa dasar izin tinggal sponsor Anda sendiri?",
  "q.family_sponsor_permit_basis.hint":
    "Pilih yang paling sesuai dengan tujuan izin tinggal sponsor Anda di Indonesia.",
  "q.family_sponsor_permit_basis.opt.EXPERT": "Tenaga ahli",
  "q.family_sponsor_permit_basis.opt.WORKER": "Pekerja (disponsori)",
  "q.family_sponsor_permit_basis.opt.MARITIME_CREW": "Awak kapal",
  "q.family_sponsor_permit_basis.opt.CLERGY": "Rohaniwan",
  "q.family_sponsor_permit_basis.opt.FOREIGN_INVESTMENT": "Investor asing",
  "q.family_sponsor_permit_basis.opt.SCIENTIFIC_RESEARCH": "Peneliti",
  "q.family_sponsor_permit_basis.opt.EDUCATION": "Pelajar",
  "q.family_sponsor_permit_basis.opt.FAMILY_REUNIFICATION":
    "Penyatuan keluarga",
  "q.family_sponsor_permit_basis.opt.REPATRIATION":
    "Repatriasi (eks warga negara Indonesia)",
  "q.family_sponsor_permit_basis.opt.SECOND_HOME": "Pemegang visa Second Home",
  "q.family_sponsor_permit_basis.opt.MEDICAL_TREATMENT": "Pengobatan medis",
  "q.family_sponsor_permit_basis.opt.WORKING_HOLIDAY": "Working holiday",
  "q.family_sponsor_permit_basis.opt.OTHER": "Dasar lain",
  "why.family_sponsor_permit_basis":
    "Beberapa dasar izin dapat menghalangi penerbitan izin penyatuan keluarga di atasnya. Kami tidak dapat memverifikasi jawaban Anda secara otomatis, sehingga tim kami yang meninjau langsung, bukan sistem yang memutuskan sendiri.",
  "q.family_marriage_registered": "Apakah pernikahan tercatat secara resmi?",
  "q.family_marriage_registered.hint":
    "Jika sponsor Anda adalah orang tua, pertanyaan ini mengenai pernikahan orang tua Anda. Pilih Tidak berlaku jika hubungan keluarga tidak melibatkan pernikahan.",
  "why.family_marriage_registered":
    "Kami memakai jawaban Anda apa adanya — ya, tidak, atau tidak tahu. Status pencatatan pernikahan tidak diasumsikan.",
  "q.family_stepchild_marriage_certificate_confirmed":
    "Dapatkah Anda memberikan akta nikah orang tua WNI Anda dan pasangan WNA-nya?",
  "q.family_stepchild_marriage_certificate_confirmed.hint":
    "Ini adalah akta nikah untuk pernikahan campuran WNI-WNA yang menjadi dasar hubungan anak tiri.",
  "why.family_stepchild_marriage_certificate_confirmed":
    "Kami menanyakan dokumen ini secara langsung. Dokumen ini tidak diasumsikan dari jawaban pernikahan tercatat di atas.",
  "q.family_stepchild_birth_certificate_confirmed":
    "Dapatkah Anda memberikan akta lahir anak tiri?",
  "q.family_stepchild_birth_certificate_confirmed.hint":
    "Akta lahir sebaiknya menunjukkan orang tua kandung yang merupakan bagian dari pernikahan campuran.",
  "why.family_stepchild_birth_certificate_confirmed":
    "Bukti akta lahir dicatat sebagai jawaban ya atau tidak tersendiri.",
  "q.family_sponsor_confirmed":
    "Apakah sponsor keluarga sudah mengonfirmasi dukungan proses?",
  "q.family_sponsor_confirmed.hint":
    "Pilih ya hanya setelah sponsor menyetujuinya.",
  "why.family_sponsor_confirmed":
    "Konfirmasi sponsor dicatat sebagai jawaban ya atau tidak tersendiri.",
  "q.retirement_penjamin_confirmed":
    "Apakah Anda sudah memiliki penjamin — biro visa berlisensi atau seseorang di Indonesia — yang akan mensponsori KITAS pensiun Anda?",
  "q.retirement_penjamin_confirmed.hint":
    "Jika belum, Bali Zero dapat bertindak sebagai penjamin Anda.",
  "why.retirement_penjamin_confirmed":
    "Konfirmasi penjamin dicatat sebagai jawaban ya atau tidak tersendiri.",

  "q.retirement_basis": "Dasar mana yang dapat Anda buktikan saat ini?",
  "q.retirement_basis.hint":
    "Ini hanya memilih pertanyaan faktual berikutnya; bukan memilih visa.",
  "q.retirement_basis.opt.bank_deposit": "Deposito bank atas nama saya",
  "q.retirement_basis.opt.property": "Pengaturan properti",
  "q.retirement_basis.opt.passive_income": "Penghasilan pasif bulanan tetap",
  "q.retirement_basis.opt.family_sponsor": "Sponsor keluarga yang dikonfirmasi",
  "q.retirement_basis.opt.undecided": "Saya belum memilih dasar",
  "why.retirement_basis":
    "Ini hanya menentukan pertanyaan berikutnya dan tidak dipakai untuk hal lain.",
  "q.retirement_undecided_basis":
    "Yang mana dari berikut yang dapat Anda buktikan saat ini?",
  "q.retirement_undecided_basis.hint":
    "Pilih dasar yang dapat Anda dukung dengan bukti. Jika tidak ada yang berlaku, sampaikan saja — tidak diperlukan peninjauan orang untuk itu.",
  "q.retirement_undecided_basis.opt.deposit_or_income":
    "Deposito bank atau penghasilan pasif yang terdokumentasi",
  "q.retirement_undecided_basis.opt.family_sponsor":
    "Sponsor keluarga yang dikonfirmasi",
  "q.retirement_undecided_basis.opt.still_unsure":
    "Saya masih belum bisa memastikan",
  "why.retirement_undecided_basis":
    "Ini juga hanya menentukan pertanyaan berikutnya, sama seperti pertanyaan dasar di atas.",
  "q.secondhome_basis":
    "Dasar Second Home mana yang dapat Anda buktikan saat ini?",
  "q.secondhome_basis.hint":
    "Pilih yang buktinya sudah Anda miliki sekarang. Gunakan Tidak yakin daripada menebak.",
  "q.secondhome_basis.opt.bank_deposit": "Deposito bank atas nama saya",
  "q.secondhome_basis.opt.property": "Properti yang memenuhi syarat",
  "why.secondhome_basis":
    "Ini hanya menentukan pertanyaan bukti berikutnya. Yang kami pakai adalah bukti yang Anda berikan, bukan pilihan ini.",
  "q.secondhome_deposit_usd": "Berapa deposito bank yang dapat Anda buktikan?",
  "q.secondhome_deposit_usd.hint":
    "Masukkan jumlah dolar bulat yang tepat; pilih Tidak yakin daripada memperkirakan.",
  "q.secondhome_deposit_usd.label": "Deposito bank terdokumentasi",
  "why.secondhome_deposit_usd":
    "Kami memakai jumlah persis yang Anda berikan. Tidak ada ambang batas yang ditampilkan di sini.",
  "q.secondhome_state_bank": "Apakah deposito berada di bank BUMN Indonesia?",
  "q.secondhome_state_bank.hint": "Jawab berdasarkan dokumen bank.",
  "why.secondhome_state_bank":
    "Jawaban ya atau tidak Anda dicatat terpisah dari jumlah deposito.",
  "q.secondhome_own_name": "Apakah seluruh deposito atas nama Anda sendiri?",
  "q.secondhome_own_name.hint":
    "Jangan gabungkan rekening atau pemilik rekening.",
  "why.secondhome_own_name":
    "Jawaban ya atau tidak Anda dicatat terpisah. Kami tidak pernah mengasumsikan kepemilikan.",
  "q.secondhome_property_value_usd":
    "Berapa nilai properti yang dapat Anda buktikan untuk rencana ini?",
  "q.secondhome_property_value_usd.hint":
    "Masukkan nilai dolar bulat yang didukung dokumen.",
  "q.secondhome_property_value_usd.label": "Nilai properti terdokumentasi",
  "why.secondhome_property_value_usd":
    "Kami memakai nilai persis yang Anda berikan. Kepemilikan dan bentuk penguasaan tidak diasumsikan dari izin tinggal.",
  "q.secondhome_passive_income_usd":
    "Berapa penghasilan pasif bulanan yang dapat Anda buktikan?",
  "q.secondhome_passive_income_usd.hint":
    "Masukkan jumlah bulanan dolar bulat yang tepat.",
  "q.secondhome_passive_income_usd.label": "Penghasilan pasif terdokumentasi",
  "why.secondhome_passive_income_usd":
    "Jumlah bulanan dipakai persis seperti yang Anda masukkan dan tidak pernah diperkirakan dari aset.",

  "q.study_level": "Tingkat studi apa yang Anda rencanakan?",
  "q.study_level.hint": "Pilih tingkat yang ditunjukkan oleh institusi.",
  "q.study_level.opt.PRIMARY": "Sekolah dasar",
  "q.study_level.opt.SECONDARY": "Sekolah menengah",
  "q.study_level.opt.VOCATIONAL": "Program vokasi",
  "q.study_level.opt.UNDERGRADUATE": "Sarjana",
  "q.study_level.opt.POSTGRADUATE": "Pascasarjana",
  "q.study_level.opt.RESEARCH": "Riset",
  "q.study_level.opt.OTHER": "Tingkat lain",
  "why.study_level": "Tingkat studi Anda dipakai persis seperti pilihan Anda.",
  "q.study_admission_confirmed":
    "Apakah institusi Indonesia sudah mengonfirmasi penerimaan Anda?",
  "q.study_admission_confirmed.hint":
    "Permohonan yang masih diproses belum berarti penerimaan terkonfirmasi.",
  "why.study_admission_confirmed":
    "Konfirmasi penerimaan dicatat sebagai jawaban ya atau tidak tersendiri.",
  "q.study_sponsor_confirmed":
    "Apakah institusi atau sponsor studi sudah mengonfirmasi dukungan?",
  "q.study_sponsor_confirmed.hint":
    "Pilih ya hanya jika sponsor sudah menyetujui.",
  "why.study_sponsor_confirmed":
    "Konfirmasi sponsor dicatat terpisah dari penerimaan.",

  "q.diaspora_connection": "Apa hubungan Anda dengan Indonesia?",
  "q.diaspora_connection.hint":
    "Ini hanya konteks untuk tim kami. Kewarganegaraan Anda ditanyakan terpisah.",
  "q.diaspora_connection.opt.former_wni": "Saya mantan warga negara Indonesia",
  "q.diaspora_connection.opt.descendant":
    "Saya keturunan warga negara Indonesia",
  "q.diaspora_connection.opt.dual":
    "Saya mungkin memiliki atau pernah memiliki lebih dari satu kewarganegaraan",
  "q.diaspora_connection.opt.family": "Hubungan saya melalui keluarga",
  "q.diaspora_connection.opt.other": "Hubungan lain",
  "why.diaspora_connection":
    "Tidak ada aturan yang didasarkan pada hubungan diaspora, jadi jawaban ini hanya disimpan sebagai konteks untuk tim kami.",
  "q.diaspora_documents": "Apakah Anda dapat membuktikan hubungan tersebut?",
  "q.diaspora_documents.hint":
    "Jangan unggah dokumen di sini; jawab hanya apakah bukti tersedia.",
  "why.diaspora_documents":
    "Ini hanya konteks manusia dan tidak dapat meningkatkan kelayakan otomatis.",

  "q.other_purpose": "Kegiatan mana yang paling dekat dengan rencana Anda?",
  "q.other_purpose.hint":
    "Konteks ini tidak diubah menjadi tujuan atau pilihan visa.",
  "q.other_purpose.opt.transit": "Transit",
  "q.other_purpose.opt.medical": "Perawatan atau pendampingan medis",
  "q.other_purpose.opt.volunteer": "Kegiatan sukarela",
  "q.other_purpose.opt.religious": "Kegiatan keagamaan",
  "q.other_purpose.opt.arts_sport": "Seni atau olahraga",
  "q.other_purpose.opt.journalism": "Jurnalistik atau media",
  "q.other_purpose.opt.crew": "Awak transportasi",
  "q.other_purpose.opt.other": "Hal lain yang tidak tercantum",
  "why.other_purpose":
    "Tidak ada satu aturan yang cocok dengan pilihan ini, jadi jawaban ini tetap menjadi konteks untuk tim kami.",
  "q.other_paid_activity": "Apakah ada bagian kegiatan ini yang dibayar?",
  "q.other_paid_activity.hint":
    "Ini hanya konteks untuk tim kami. Jawaban ini tidak diubah menjadi jawaban ketenagakerjaan.",
  "why.other_paid_activity":
    "Tidak ada aturan yang tepat untuk pertanyaan luas ini, sehingga jawabannya tidak dapat mendukung rekomendasi.",

  "q.stay_days": "Berapa hari Anda berencana tinggal?",
  "q.stay_days.hint":
    "Masukkan jumlah hari penuh yang direncanakan; angka ini bukan ambang hukum.",
  "q.stay_days.label": "Rencana masa tinggal",
  "q.stay_days.unit": "hari",
  "why.stay_days":
    "Kami memeriksa durasi persis yang Anda rencanakan, bukan menebak dari rentang yang luas.",

  "q.review_gate": "Ada hal lain yang perlu kami ketahui?",
  "q.review_gate.hint":
    "Centang semua yang berlaku — tidak menyebutkannya lebih merugikan Anda daripada menyebutkannya. Sebagian di antaranya, termasuk catatan kriminal, membuat kasus Anda ditinjau seseorang sebelum ada keputusan; sisanya menyertai hasil Anda sebagai kondisi tersurat yang ditelusuri tim kami bersama Anda sebelum pengajuan.",
  "why.review_gate":
    "Setiap item di sini diperhitungkan: tiga item riwayat keimigrasian berpengaruh langsung pada aturan, dan semuanya harus tercermin dalam hasil Anda.",
  "q.review_gate.opt.none": "Tidak ada yang berlaku bagi saya",
  "q.review_gate.opt.flagged": "Satu atau lebih berlaku",
  "q.review_gate.item.none": "Tidak ada yang berlaku bagi saya",
  "q.review_gate.item.criminal_record": "Catatan kriminal, di mana pun",
  "q.review_gate.item.health_flag":
    "Kondisi kesehatan yang mungkin ditanyakan imigrasi",
  "q.review_gate.item.prior_refusal": "Penolakan visa sebelumnya",
  "q.review_gate.item.overstay": "Riwayat overstay",
  "q.review_gate.item.blacklist": "Masuk daftar hitam",
  "q.review_gate.item.immigration_investigation": "Pemeriksaan keimigrasian",
  "q.review_gate.item.pep_or_sanctions": "Kekhawatiran terkait PEP atau sanksi",
  "q.review_gate.item.source_of_funds_unclear":
    "Bukti sumber dana belum jelas atau belum lengkap",
  "q.review_gate.item.diplomatic_passport": "Paspor diplomatik",
  "q.review_gate.item.ambiguous_sponsor": "Calon sponsor belum jelas",
  "q.review_gate.item.activity_boundary":
    "Kegiatan yang direncanakan mungkin melintasi beberapa kategori",
  "q.review_gate.item.not_certain": "Saya tidak yakin soal semua di atas",
  "q.review_gate.none_selected": "Tidak ada yang berlaku bagi saya",

  "notsure.trigger": "Tidak yakin?",
  "assumption.in_indonesia":
    "Anda tidak yakin di mana posisi Anda, jadi kami mencatatnya sebagai hal yang belum dipastikan alih-alih menganggapnya, dan konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.permit_expiry":
    "Anda belum yakin kapan izin tinggal saat ini berakhir, jadi tidak ada tenggat yang diperkirakan.",
  "assumption.stay_days":
    "Anda belum yakin tentang rencana masa tinggal, jadi tidak ada durasi yang diperkirakan.",
  "assumption.work_payer":
    "Anda tidak yakin siapa yang menggaji Anda, jadi kami mencatatnya sebagai hal yang belum dipastikan; kami tetap menilai semua yang bisa dinilai, dan konsultan Bali Zero akan memastikan poin ini bersama Anda.",
  "assumption.remote_clients":
    "Anda tidak yakin di mana klien Anda berada, jadi kami mencatatnya sebagai hal yang belum dipastikan; kami tetap menilai semua yang bisa dinilai, dan konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.secondhome_deposit_usd":
    "Anda tidak yakin berapa deposito bank yang dapat Anda buktikan, jadi rencana ini kami nilai seolah depositonya nol; konsultan Bali Zero akan memastikan angka sebenarnya bersama Anda.",
  "assumption.secondhome_property_value_usd":
    "Anda tidak yakin berapa nilai properti yang dapat Anda buktikan, jadi rencana ini kami nilai seolah nilai propertinya nol; konsultan Bali Zero akan memastikan angka sebenarnya bersama Anda.",
  "assumption.secondhome_passive_income_usd":
    "Anda tidak yakin berapa penghasilan pasif bulanan yang dapat Anda buktikan, jadi rencana ini kami nilai seolah penghasilan itu nol; konsultan Bali Zero akan memastikan angka sebenarnya bersama Anda.",
  "assumption.secondhome_state_bank":
    "Anda tidak yakin apakah deposito itu ditempatkan di bank BUMN Indonesia, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.secondhome_own_name":
    "Anda tidak yakin apakah seluruh deposito itu atas nama Anda sendiri, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.study_admission_confirmed":
    "Anda tidak yakin apakah institusi di Indonesia sudah mengonfirmasi penerimaan Anda, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.study_sponsor_confirmed":
    "Anda tidak yakin apakah institusi atau sponsor studi sudah mengonfirmasi dukungannya, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.diaspora_documents":
    "Anda tidak yakin apakah Anda dapat membuktikan hubungan tersebut, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.retirement_basis":
    "Anda tidak yakin dasar mana yang dapat Anda buktikan saat ini, jadi rencana ini kami nilai seolah Anda belum memilih dasar; konsultan Bali Zero akan memastikannya bersama Anda.",
  "assumption.retirement_penjamin_confirmed":
    "Anda tidak yakin apakah Anda sudah memiliki penjamin, jadi rencana ini kami nilai seolah jawabannya “tidak”; Bali Zero dapat bertindak sebagai penjamin Anda.",
  "assumption.generic":
    "Anda memilih “Tidak yakin” untuk “{{question}}”; tidak ada nilai yang diperkirakan.",

  "whyweask.trigger": "Mengapa kami tanyakan ini",
  "whyweask.trigger.aria": "Mengapa kami menanyakan pertanyaan ini",
  "whyweask.fact_prefix": "Dipakai untuk memutuskan: {{facts}}",
  "whyweask.review_only":
    "Ditandai untuk ditinjau; hanya rincian berikut yang dipakai: {{facts}}",
  "whyweask.human_context":
    "Hanya untuk konteks tim kami — tidak dipakai untuk memutuskan apa pun.",

  "back.button": "Kembali",
  "question.continue": "Lanjutkan",
  "question.human_context_notice":
    "Hanya konteks manusia — jawaban ini tidak dapat memilih, mengurutkan, menambah, atau menghapus jalur visa.",
  "question.invalid_country_codes":
    "Pilih negara dari daftar terverifikasi, atau pilih Tidak tercantum.",
  "question.country_picker.placeholder": "Pilih negara",
  "question.country_picker.search": "Cari negara",
  "question.country_picker.search_placeholder": "Ketik nama negara…",
  "question.country_picker.not_listed": "Lainnya / tidak tercantum",
  "question.country_picker.add": "Tambah negara",
  "question.country_picker.selected": "Negara terpilih",
  "question.country_picker.remove": "Hapus {{country}}",
  "question.country_picker.max":
    "Anda dapat menambahkan hingga {{count}} negara paspor. Hapus satu untuk memilih yang lain.",
  "question.invalid_status_code":
    "Masukkan kode izin persis seperti di dokumen, hanya dengan huruf dan angka.",
  "restart.button": "Mulai ulang",
  "verdict.edit_answers": "Ubah jawaban",

  "tree.edit_aria": "Ubah jawaban: {{question}}",
  "tree.breadcrumb_label": "Cabang wawancara saat ini",
  "tree.framing": "Mulai",
  "tree.in_indonesia": "Posisi Anda",
  "tree.permit_expiry": "Jendela izin tinggal",
  "tree.holds_stay_permit": "Izin tinggal",
  "tree.current_status_code": "Status saat ini",
  "tree.stay_permit_code": "Kode izin",
  "tree.renewal_paid": "Pembayaran perpanjangan",
  "tree.overstay_days": "Overstay aktif",
  "tree.wants_onshore_conversion": "Niat konversi",
  "tree.application_channel": "Kanal permohonan",
  "tree.nationalities": "Paspor",
  "tree.birth_date": "Pemeriksaan usia",
  "tree.category": "Kategori",
  "tree.trip_scope": "Tujuan perjalanan",
  "tree.entry_pattern": "Pola masuk",
  "tree.sponsor_category": "Kategori sponsor",
  "tree.business_activity": "Kegiatan bisnis",
  "tree.business_sponsor_confirmed": "Sponsor perusahaan",
  "tree.work_payer": "Siapa yang menggaji",
  "tree.work_indonesia_compensation": "Sumber pembayaran",
  "tree.work_sponsor_confirmed": "Sponsor kerja",
  "tree.sponsor_government_invitation": "Undangan pemerintah",
  "tree.sponsor_government_collaboration": "Kolaborasi pemerintah",
  "tree.sponsor_world_figure_invitation": "Undangan tokoh dunia",
  "tree.sponsor_diplomatic_household": "Rumah tangga diplomat",
  "tree.sponsor_trade_office": "Penjamin kantor dagang",
  "tree.remote_clients": "Lokasi klien",
  "tree.remote_compensation": "Sumber pembayaran",
  "tree.remote_employer_country": "Negara pemberi kerja",
  "tree.remote_pt_pma": "Kaitan PT PMA",
  "tree.stay_days": "Lama tinggal",
  "tree.investment_vehicle": "Dasar investasi",
  "tree.investment_pt_pma": "Komitmen PT PMA",
  "tree.investment_capital_idr": "Modal investasi",
  "tree.investment_paid_up_capital_idr": "Modal disetor",
  "tree.investment_role": "Peran perusahaan",
  "tree.investment_establishes_company": "Perusahaan di Indonesia",
  "tree.investment_foreign_branch": "Cabang atau anak perusahaan asing",
  "tree.investment_ikn_subsidiary": "Anak perusahaan di IKN",
  "tree.investment_capital_market_only": "Hanya pasar modal",
  "tree.investment_meets_threshold": "Batas minimum terpublikasi",
  "tree.family_relation": "Hubungan keluarga",
  "tree.marital_status": "Status perkawinan",
  "tree.family_sponsor_nationalities": "Paspor sponsor",
  "tree.family_sponsor_status_code": "Status sponsor",
  "tree.family_sponsor_permit_basis": "Dasar izin sponsor",
  "tree.family_marriage_registered": "Catatan pernikahan",
  "tree.family_stepchild_marriage_certificate_confirmed":
    "Akta nikah orang tua",
  "tree.family_stepchild_birth_certificate_confirmed": "Akta lahir",
  "tree.family_sponsor_confirmed": "Sponsor keluarga",
  "tree.retirement_penjamin_confirmed": "Penjamin pensiun",
  "tree.retirement_basis": "Dasar tinggal panjang",
  "tree.secondhome_basis": "Dasar Second Home",
  "tree.secondhome_deposit_usd": "Deposito bank",
  "tree.secondhome_state_bank": "Jenis bank",
  "tree.secondhome_own_name": "Pemilik rekening",
  "tree.secondhome_property_value_usd": "Nilai properti",
  "tree.secondhome_passive_income_usd": "Penghasilan pasif",
  "tree.study_level": "Tingkat studi",
  "tree.study_admission_confirmed": "Penerimaan",
  "tree.study_sponsor_confirmed": "Sponsor studi",
  "tree.diaspora_connection": "Konteks diaspora",
  "tree.diaspora_documents": "Bukti hubungan",
  "tree.other_purpose": "Konteks kegiatan",
  "tree.other_paid_activity": "Kegiatan berbayar",
  "tree.review_gate": "Pemeriksaan keamanan",
  "tree.confirmation": "Jawaban Anda",
  "tree.verdict": "Hasil",
  "tree.sr_path_label": "Jalur Anda sejauh ini",
  "tree.sr_status.done": "sudah dijawab",
  "tree.sr_status.current": "langkah saat ini",
  "tree.sr_status.pending": "belum tercapai",
  "tree.sr_status.pruned": "cabang wawancara berbeda",

  "process.label": "Posisi Anda dalam proses ini",
  "process.step_of": "{{current}} dari {{total}} terjawab",
  "process.phases_label": "Tahapan",
  "process.phase.location": "Posisi Anda",
  "process.phase.identity": "Identitas Anda",
  "process.phase.intent": "Tujuan kedatangan Anda",
  "process.phase.details": "Rincian tujuan tersebut",
  "process.phase.review": "Pemeriksaan keamanan dan jawaban Anda",
  "process.phase.outcome": "Hasil Anda",
  "process.phase_status.done": "selesai",
  "process.phase_status.current": "sedang berjalan",
  "process.phase_status.partial": "sedang berlangsung",
  "process.phase_status.pending": "belum dimulai",
  "process.phase_status.pruned": "bukan cabang ini",
  "process.decides_title": "Yang ditentukan pertanyaan ini",
  "process.decides_fact":
    "Jawaban Anda menetapkan rincian berikut, yang kami pakai:",
  "process.decides_review":
    "Jawaban Anda adalah sinyal keamanan: kasus ini dapat diteruskan ke konsultan Bali Zero, dan tidak pernah dibaca sebagai kelayakan.",
  "process.decides_context":
    "Pertanyaan ini tidak menetapkan rincian tersendiri. Pertanyaan ini mengarahkan pertanyaan berikutnya, dan masih dapat menjadi bagian dari sesuatu yang kami simpulkan dari jawaban Anda secara keseluruhan.",
  "process.decides_none":
    "Tidak ada pertanyaan yang terbuka. Kami sudah menerima jawaban yang Anda konfirmasi.",
  "process.decides_awaiting":
    "Tidak ada pertanyaan yang terbuka. Jawaban Anda sudah dikonfirmasi; hasil Anda belum tampil di layar.",
  "process.decides_framing":
    "Belum ada yang dijawab. Setiap pertanyaan menjelaskan apa yang ditentukan jawabannya sebelum Anda menjawab.",
  "process.decides_confirmation":
    "Tidak ada pertanyaan yang terbuka. Mengonfirmasi jawaban inilah yang memeriksa kasus Anda — dan memeriksanya lagi jika Anda pernah ke sini.",
  "process.categories_title": "Cabang tujuan",
  "process.category_status.current": "terbuka — sedang ditanyakan",
  "process.category_status.done": "sudah dijawab",
  "process.category_status.pruned": "ditutup",
  "process.category_status.pending": "masih terbuka",
  "process.pruned_because":
    "{{count}} cabang ditutup ketika Anda memilih “{{category}}”. Jawaban di dalam cabang ini tidak dapat membukanya kembali — kembali ke pertanyaan tujuan untuk mengganti cabang.",
  "process.pruned_none":
    "Semua cabang tujuan masih terbuka. Memilih satu akan menutup yang lain.",
  "process.candidates_title": "Pilihan yang kami temukan untuk Anda",
  "process.candidates_pending":
    "Belum ada pilihan yang disebut. Kami baru memeriksa kasus Anda setelah Anda mengonfirmasi jawaban — alat ini tidak pernah memutuskan kelayakan sendiri.",
  "process.candidates_none":
    "Kami tidak menemukan pilihan untuk jawaban ini. Hasil di bawah menjelaskan alasannya.",
  "process.candidates_undecided":
    "Kami belum dapat menyebut pilihan untuk jawaban ini. Hasil di bawah menjelaskan alasannya.",
  "process.candidates_follow_up":
    "Kami sudah menerima jawaban Anda dan masih memerlukan satu rincian lagi sebelum dapat memutuskan. Pertanyaan ini menanyakannya.",
  "process.outcome_node":
    "Anda berada di simpul terakhir pohon ini: hasil di bawah adalah simpul tersebut, bukan halaman terpisah.",
  "process.jump_title": "Kembali ke sebuah jawaban",
  "process.jump_aria": "Kembali ke {{question}} — Anda menjawab {{answer}}",
  "process.jump_empty": "Belum ada jawaban untuk dituju.",
  "process.answer_unsure": "Tidak yakin",
  "process.announce_prune":
    "Anda memilih {{category}}. {{count}} cabang tujuan lainnya ditutup.",

  "paths.counter.label": "{{count}} cabang wawancara",
  "paths.counter.aria": "{{count}} cabang wawancara tersisa",

  "confirmation.title": "Berikut yang Anda sampaikan",
  "confirmation.your_answers": "Jawaban Anda",
  "confirmation.group.location": "Situasi saat ini",
  "confirmation.group.identity": "Tentang Anda",
  "confirmation.group.intent": "Tujuan Anda",
  "confirmation.group.details": "Rincian cabang",
  "confirmation.group.review": "Sinyal tinjauan",
  "confirmation.assumptions_title": "Asumsi yang kami buat",
  "confirmation.edit": "Ubah",
  "confirmation.paths_remaining": "{{count}} cabang wawancara tersisa",
  "confirmation.price_preview":
    "Jika layanan Bali Zero yang didukung memiliki harga terverifikasi, harganya akan tampil sebagai satu jumlah all-inclusive.",
  "confirmation.cta": "Lihat opsi saya",

  "verdict.headline.SUPPORTED_CANDIDATES": "Ada jalan ke depan.",
  "verdict.headline.HUMAN_REVIEW_REQUIRED":
    "Ini butuh manusia, bukan algoritma",
  "verdict.headline.NO_SUPPORTED_PATH":
    "Jalur persis ini belum didukung — ini alternatifnya",
  "verdict.headline.TEMPORARILY_UNAVAILABLE": "Jeda sejenak dalam perjalanan.",
  "verdict.headline.NEEDS_INPUT": "Sedikit lagi",
  "verdict.headline.SECOND_HOME_STUDIO":
    "Di bawah ambang batas jaminan Second Home",
  "verdict.evaluating": "Memeriksa opsi Anda…",
  "verdict.eligibility.eligible": "Memenuhi syarat",
  "verdict.eligibility.likely": "Kemungkinan besar",
  "verdict.eligibility.conditional": "Bersyarat",
  "verdict.eligibility.likely-not": "Kemungkinan tidak",
  "verdict.state_description.SUPPORTED_CANDIDATES":
    "Opsi-opsi ini sesuai dengan jawaban yang Anda berikan.",
  "verdict.state_description.HUMAN_REVIEW_REQUIRED":
    "Tidak ada yang ditebak di sini. Konsultan Bali Zero meninjau kasus seperti ini secara langsung.",
  "verdict.state_description.NO_SUPPORTED_PATH":
    "Kami tidak akan memaksakan jalur yang tidak cocok — inilah yang dibuka oleh jawaban Anda.",
  "verdict.state_description.TEMPORARILY_UNAVAILABLE":
    "Kami belum bisa memeriksa opsi Anda saat ini. Jawaban Anda masih ada di halaman ini.",
  "verdict.state_description.NEEDS_INPUT":
    "Selesaikan wawancara untuk melihat opsi Anda.",
  "verdict.state_description.SECOND_HOME_STUDIO":
    "Angka jaminan yang Anda nyatakan belum mencapai ambang batas Rumah Kedua (E33). Alasannya, dan tempat memeriksa jalur lainnya, ada tepat di bawah.",
  "verdict.provenance_headline.CLIENT_GUARD":
    "Satu jawaban perlu diperjelas terlebih dahulu",
  "verdict.provenance_headline.NETWORK_FAILURE":
    "Layanan keputusan tidak dapat dihubungi",
  "verdict.provenance_headline.SHADOW":
    "Verifikasi penilaian sedang berlangsung",
  "verdict.provenance_headline.PREVIEW":
    "Hanya pratinjau — bukan keputusan langsung",
  "verdict.provenance_description.CLIENT_GUARD":
    "Belum ada keputusan yang dibuat. Tinjau jawaban yang ditandai atau lanjutkan dengan konsultan.",
  "verdict.provenance_description.NETWORK_FAILURE":
    "Tidak ada hasil yang dibuat. Jawaban Anda tidak diganti dengan tebakan.",
  "verdict.provenance_description.SHADOW":
    "Penilaian Anda dicatat untuk verifikasi; tidak ada jalur visa yang ditampilkan dalam mode ini.",
  "verdict.provenance_description.PREVIEW":
    "Layar ini memakai data uji untuk peninjauan produk dan tidak dapat mendukung rekomendasi.",

  "outcome.timeline_title": "Linimasa",
  "outcome.timeline_pending":
    "Lama proses ditentukan oleh Ditjen Imigrasi dan bervariasi menurut kantor dan musim. Konsultan Bali Zero memastikan jadwal untuk kasus Anda sebelum Anda memesan perjalanan.",
  "outcome.path_counter": "Jalur {{index}} dari {{total}}",
  "outcome.checked_on": "Diperiksa pada {{date}} berdasarkan sumber di atas.",
  "outcome.checked_on_plain": "Diperiksa pada {{date}}.",
  "outcome.price_label": "Harga all-inclusive",
  "outcome.price_all_inclusive":
    "Sudah termasuk biaya pemerintah dan jasa Bali Zero.",
  "outcome.price_valid_until": "Penawaran berlaku hingga {{date}}",
  "outcome.price_free": "Gratis",
  "outcome.whatsapp_summary_header": "Ringkasan keputusan Visa Oracle:",
  "outcome.checklist_title": "Dokumen yang perlu Anda siapkan",
  "outcome.next_steps_title": "Langkah berikutnya",
  "outcome.whatsapp_cta": "Lanjutkan di WhatsApp",
  "outcome.qr_aria":
    "Kode QR — pindai untuk melanjutkan ringkasan ini di WhatsApp lewat ponsel Anda",
  "outcome.print_cta": "Cetak / simpan sebagai PDF",
  "outcome.copy_cta": "Salin ringkasan",
  "outcome.copy_confirmed": "Disalin ke papan klip",
  "outcome.copy_failed": "Gagal menyalin — coba pilih teksnya secara manual",
  "outcome.share_title": "Ringkasan keputusan Visa Oracle",
  "outcome.share_cta": "Bagikan ringkasan",
  "outcome.share_confirmed": "Dibagikan",
  "outcome.decision_reference": "Referensi keputusan: {{id}}",
  "outcome.supported_paths": "Jalur yang didukung",
  "outcome.rank": "Peringkat {{rank}}",
  "outcome.axis.legal": "Kelayakan hukum",
  "outcome.axis.operational": "Ketersediaan saat ini",
  "outcome.axis.service": "Layanan Bali Zero",
  "outcome.status.SUPPORTED": "Didukung",
  "outcome.status.CONDITIONAL": "Bersyarat",
  "outcome.status.NOT_SUPPORTED": "Tidak didukung",
  "outcome.status.UNKNOWN": "Belum diketahui",
  "outcome.status.AVAILABLE": "Tersedia",
  "outcome.status.TEMPORARILY_UNAVAILABLE": "Sementara tidak tersedia",
  "outcome.status.CONTACT_REQUIRED": "Perlu menghubungi kami",
  "outcome.status.NOT_OFFERED": "Tidak ditawarkan",
  "outcome.why_supported": "Mengapa jalur ini didukung",
  "outcome.timeline_dates": "{{from}} sampai {{to}}",
  "outcome.timeline_basis": "Dihitung dari tanggal penilaian: {{date}}",
  "outcome.document_status.CONDITIONAL": "Bersyarat",
  "outcome.document_status.UNKNOWN": "Perlu dikonfirmasi",
  "outcome.needs_input_body": "Beberapa detail masih kurang:",
  "outcome.answer_missing_input": "Jawab ini",
  "outcome.retryable": "Anda dapat mencoba evaluasi ini kembali dengan aman.",
  "outcome.not_retryable":
    "Konsultan Bali Zero perlu memeriksanya sebelum Anda melanjutkan.",
  "outcome.sources_title": "Sumber yang digunakan untuk keputusan ini",
  "outcome.source_dates":
    "Berlaku sejak {{effective}} · terakhir diperiksa {{observed}}",
  "outcome.freshness.CURRENT": "Terkini",
  "outcome.freshness.STALE": "Sedang diperiksa ulang oleh tim kami",
  "outcome.freshness.UNKNOWN": "Tanggal pemeriksaan terakhir tidak diketahui",
  "outcome.provenance.CLIENT_GUARD.title": "Akan ditinjau oleh seseorang",
  "outcome.provenance.CLIENT_GUARD.body":
    "Jawaban Anda perlu ditinjau seseorang sebelum jalur dapat ditampilkan.",
  "outcome.provenance.NETWORK_FAILURE.title":
    "Layanan keputusan tidak tersedia",
  "outcome.provenance.NETWORK_FAILURE.body":
    "Layanan keputusan tidak dapat dihubungi. Tidak ada yang ditebak — silakan coba lagi dalam beberapa menit.",
  "outcome.provenance.SHADOW.title": "Mode verifikasi",
  "outcome.provenance.SHADOW.body":
    "Penilaian ini dicatat untuk verifikasi; tidak ada jalur visa yang ditampilkan dalam mode ini.",
  "outcome.provenance.PREVIEW.title": "Data pratinjau",
  "outcome.provenance.PREVIEW.body":
    "Konten ini hanya untuk pengujian dan bukan rekomendasi.",
  "outcome.assumptions_receipt_title": "Yang kami asumsikan",
  "outcome.assumptions_receipt_empty":
    "Tidak ada asumsi yang diperlukan — semua jawaban diberikan langsung.",
  "outcome.freshness_stamp": "Diperiksa berdasarkan aturan pada {{date}}",
  "outcome.disclaimer.not_government":
    "Ini alat bantu keputusan privat, bukan layanan pemerintah.",
  "outcome.disclaimer.based_on_facts":
    "Hasil ini hanya mencerminkan data yang Anda masukkan dan sumber bertanggal yang ditampilkan di atas.",
  "outcome.disclaimer.not_approval":
    "Ini bukan persetujuan, jaminan, atau pengajuan resmi.",
  "outcome.disclaimer.complex_to_human":
    "Jika Anda mengungkapkan catatan kriminal, atau memberi jawaban yang tidak dapat dinilai oleh aturan ini, konsultan Bali Zero meninjau kasus Anda sebelum jalur mana pun dikonfirmasi. Pengungkapan lainnya tampil pada hasil Anda sebagai syarat yang kami periksa bersama Anda sebelum pengajuan. Keputusan selalu di tangan Ditjen Imigrasi, bukan alat ini.",
  // Never "penahanan" (detention) for a decision hold: this is immigration copy.
  "outcome.disclaimer.second_home_studio":
    "Hasil ini berkaitan dengan angka jaminan yang Anda nyatakan, yang masih di bawah ambang batas Rumah Kedua (E33) — Second Home Studio menampilkan jalur-jalur dan angka untuk kasus Anda.",
  "outcome.alternatives_title": "Pintu yang terbuka",
  "outcome.alternatives_intro":
    "Jalur lain yang dapat dipastikan alat ini untuk Anda.",
  "outcome.no_path_body":
    "Kombinasi yang Anda jelaskan tidak cocok dengan jalur visa mana pun yang dapat dipastikan alat ini.",
  "outcome.temporarily_unavailable_body":
    "Pemeriksaan tidak dapat dijalankan saat ini. Silakan coba lagi dalam beberapa menit.",
  "outcome.human_review_body":
    "Kasus Anda perlu ditinjau konsultan Bali Zero — kami tidak menebak apa pun untuk Anda.",
  "outcome.conditions.title": "Sebelum Anda mengajukan",
  "outcome.conditions.intro":
    "Hasil di atas diperoleh dengan kondisi-kondisi berikut yang menyertainya. Tim kami akan memeriksa setiap kondisi bersama Anda sebelum pengajuan.",
  "outcome.review_group_case.title":
    "Yang akan diperiksa konsultan Bali Zero pada kasus Anda",
  "outcome.review_group_system.title":
    "Pemeriksaan di pihak kami, bukan pada jawaban Anda",
  "outcome.review.element.rule": "Mengapa hasil ini ditunda",
  "outcome.review.element.checked": "Apa yang diperiksa peninjau",
  "outcome.review.element.prepare": "Apa yang perlu disiapkan",
  "outcome.review.element.handling": "Bagaimana hal ini ditangani",
  "outcome.review_cause_unsure":
    "Anda menjawab “Tidak yakin” pada: {{question}}",
  "outcome.review_cause_answer":
    "Anda menjawab “{{answer}}” pada: {{question}}",
  "outcome.review_cause_edit_aria": "Ubah jawaban Anda pada: {{question}}",
  "outcome.overstay_reassurance":
    "Overstay bisa diselesaikan. Ini bukan akhir cerita Anda di sini.",
  "outcome.second_home_studio_link": "Buka Second Home Studio",

  "prototype.badge": "Dukungan keputusan visa",
  "prototype.badge.detail":
    "Hanya jalur yang dapat dipastikan alat ini yang tampil sebagai jalur yang didukung.",

  "theme.toggle.aria": "Ganti antara mode terang dan gelap",
  "theme.toggle.light": "Terang",
  "theme.toggle.dark": "Gelap",
  "language.toggle.aria": "Ganti bahasa",
  "language.option.en": "EN",
  "language.option.id": "ID",
  "language.option.en.aria": "Ganti ke bahasa Inggris",
  "language.option.id.aria": "Ganti ke Bahasa Indonesia",

  "footer.disclaimer":
    "Visa Oracle adalah alat bantu keputusan privat. Ini bukan layanan pemerintah, persetujuan, atau pengajuan — Ditjen Imigrasi yang memutuskan. Kasus yang tidak diketahui atau kompleks ditinjau manusia.",
  "footer.privacy": "Kebijakan privasi Visa Oracle",
  "process.branch_preview_more": "dan {{count}} pertanyaan lagi",
  "process.branch_reopen_aria":
    "Beralih ke {{category}} — membuka kembali cabang ini dan menanyakan pertanyaannya",
  "tree.investment_currency": "Mata uang investasi",
  "tree.investment_amount_usd": "Jumlah investasi",
  "tree.retirement_undecided_basis": "Jalur tinggal panjang",

  "outcome.why_fits": "Mengapa ini cocok",
  "outcome.reason_generic":
    "Penilaian mendukung opsi ini untuk jawaban yang Anda berikan.",
  "outcome.legal_references": "Dasar hukum",
  "outcome.reason_generic_no_path":
    "Jalur ini tidak didukung untuk jawaban yang Anda berikan.",
};

export const dict = { en, id };

/** Finding #16 (adversarial review 2026-07-17): design doc §3's ID register
 * rule is "body-first, warm-formal" — Indonesian readers of this register
 * expect the explanatory sentence before the terse headline, the reverse
 * of the EN "headline, then body" convention this route was built with
 * throughout. Consumers that render a heading+body pair (VerdictReveal)
 * read this flag to swap the render order per language rather than
 * hardcoding the EN ordering everywhere. */
export const BODY_FIRST: Record<Language, boolean> = { en: false, id: true };

/** Matches `{{plural:singular|plural}}` markers — see `translate()` below.
 * Kept as a plain literal-string marker (not a `{{count}}`-style var) so an
 * English string can carry the ONE irregular plural it needs ("branch" →
 * "branches") without a second interpolation pass at every call site. */
const PLURAL_MARKER_RE = /\{\{plural:([^|{}]*)\|([^{}]*)\}\}/g;

/** Simple `{{var}}` interpolation, plus one narrow pluralization escape
 * hatch: `{{plural:singular|plural}}` resolves to `singular` when
 * `vars.count === 1`, else `plural` — still not full ICU pluralization
 * (this file does not need that at its current scale), just enough to stop
 * "1 interview branches" reading as a typo. Bahasa Indonesia does not
 * inflect nouns for number, so ID strings simply never use the marker.
 * Missing keys return the raw key (visibly broken, never silent). */
export function translate(
  language: Language,
  key: Keys,
  vars?: Record<string, string | number>,
): string {
  const table = dict[language];
  let value: string = table[key] ?? key;
  if (vars) {
    for (const [name, v] of Object.entries(vars)) {
      value = value.replaceAll(`{{${name}}}`, String(v));
    }
    if (typeof vars.count === "number") {
      const count = vars.count;
      value = value.replace(
        PLURAL_MARKER_RE,
        (_match, singular: string, plural: string) =>
          count === 1 ? singular : plural,
      );
    }
  }
  return value;
}

export type { Keys as I18nKey };

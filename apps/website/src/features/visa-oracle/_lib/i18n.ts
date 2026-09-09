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
    "Answer honestly, including “I don’t know.” Nothing here is filed, and the interface never chooses a visa path on its own.",
  "framing.cta": "Start",

  "q.in_indonesia": "Are you in Indonesia right now?",
  "q.in_indonesia.hint": "This decides which questions matter next.",
  "q.in_indonesia.opt.yes": "Yes, I’m here",
  "q.in_indonesia.opt.no": "No, I’m planning ahead",
  "why.in_indonesia":
    "Your current location tells the engine whether this is an onshore situation or a future plan.",

  "q.permit_expiry": "When does your current stay permit expire?",
  "q.permit_expiry.hint":
    "The date on your visa or ITAS/KITAS — not your passport.",
  "q.permit_expiry.label": "Expiry date",
  "why.permit_expiry":
    "The engine needs the date itself to assess timing; this interface does not infer a filing route from it.",
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
    "The engine receives the printed status code unchanged; the interface never guesses it from the permit name.",
  "q.holds_stay_permit":
    "Do you currently hold a limited or permanent stay permit (KITAS / KITAP)?",
  "why.holds_stay_permit":
    "This selects the next permit question. If you answer No and no printed status code is collected, the engine records that you do not hold a stay permit. Yes requires the exact code; it does not establish a permit type.",
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
    "The engine receives the printed code unchanged, the same as the code list above — the interface never guesses it from the permit name.",

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
    "Active overstay days are a separate safety-critical fact. They are never derived from the expiry date in the browser.",
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
    "This exact yes/no process fact is sent without choosing a conversion path.",
  "q.application_channel":
    "Which application channel are you actually pursuing?",
  "q.application_channel.hint":
    "Choose only a channel already confirmed for your case, or use Not sure.",
  "q.application_channel.opt.OFFSHORE": "Apply after leaving Indonesia",
  "q.application_channel.opt.ONSHORE_CONVERSION": "Onshore status conversion",
  "q.application_channel.opt.STATUS_BRIDGING": "Status bridging process",
  "why.application_channel":
    "The selected closed-enum channel is sent unchanged. The interface never assigns a channel from your dates.",
  "q.application_channel.conflict":
    "That channel doesn’t match your earlier answer about changing status without leaving Indonesia. Go back and correct one of the two answers — we won’t guess which one is right.",

  "q.nationalities": "Which nationalities appear on your passports?",
  "q.nationalities.hint":
    "Choose each passport country. The stored answer remains a language-independent country code.",
  "q.nationalities.label": "Passport countries",
  "why.nationalities":
    "Nationality is checked as an exact decision fact. Multiple nationalities stay separate and are never guessed.",
  "q.birth_date": "What is your date of birth?",
  "q.birth_date.hint":
    "We send the date as a decision fact; the engine derives age consistently.",
  "q.birth_date.label": "Date of birth",
  "why.birth_date":
    "Some paths distinguish adults and minors. The interface does not calculate eligibility from your age.",

  "lane.expired.notice":
    "Your permit has already expired. Overstay is fixable. It is not the end of your story here — this always goes to a human, and we won’t alarm you with a number on this screen.",
  "lane.urgent.notice":
    "You have 1–2 days left. That’s too close for an automated routing — a Bali Zero advisor needs to look at this today.",
  "lane.bridging.notice":
    "The date you entered is within seven days. The engine may abstain and ask for human review; this interface will not select a bridge or conversion route.",
  "lane.extend.notice":
    "You have time to compare Extend and Convert side by side.",
  "lane.planning.notice": "Plenty of runway — this is planning, not urgency.",

  "q.category": "What brings you to Indonesia?",
  "q.category.hint": "Pick the closest fit — you can refine it next.",
  "why.category":
    "This is a soft interview branch. Only the engine can decide whether any visa path is supported.",
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
    "Overlapping purposes need context from a person. This answer is not translated into an engine fact.",
  "q.entry_pattern": "How do you expect to enter Indonesia?",
  "q.entry_pattern.hint": "Choose the pattern you are actually planning.",
  "q.entry_pattern.opt.SINGLE": "One entry",
  "q.entry_pattern.opt.MULTIPLE": "More than one entry",
  "why.entry_pattern":
    "The engine receives SINGLE or MULTIPLE exactly as selected.",

  "q.sponsor_category": "Who sponsors your stay in Indonesia?",
  "q.sponsor_category.hint":
    "Choose the party that provides or backs your permit, not who pays your day-to-day bills.",
  "q.sponsor_category.opt.NONE": "I do not have a sponsor",
  "q.sponsor_category.opt.INDIVIDUAL":
    "An individual (a family or personal sponsor)",
  "q.sponsor_category.opt.EMPLOYER": "An employer — a company in Indonesia",
  "q.sponsor_category.opt.EDUCATION": "An educational institution",
  "q.sponsor_category.opt.INVESTMENT": "An investment or company I own",
  "q.sponsor_category.opt.GOVERNMENT": "A government body",
  "why.sponsor_category":
    "Some routes require a particular type of sponsor. This answer identifies the sponsor; it does not confirm that you qualify.",

  "q.business_activity": "What will you mainly do on the business trip?",
  "q.business_activity.hint": "Describe what you will do. Surveys and feasibility studies to start a business are different from ordinary commercial visits. Training, operational work and uncertain activities need review.",
  "q.business_activity.opt.meetings": "Commercial meetings or customer/site visits",
  "q.business_activity.opt.negotiation": "Negotiation or signing",
  "q.business_activity.opt.conference": "Attend a conference or trade event as a participant",
  "q.business_activity.opt.training": "Giving or receiving training",
  "q.business_activity.opt.other": "Another business activity",
  "why.business_activity": "Pre-investment exploration is sent as investment intent. Other activities keep the Business purpose; ordinary meetings, negotiations, conferences, training and unspecified activity need review because the current activity vocabulary cannot safely distinguish all visa scopes.",

  "q.work_payer":
    "Is your employing entity registered in Indonesia?",
  "q.work_payer.hint":
    "Answer about your legal employer, not where payment comes from. We ask about compensation separately.",
  "why.work_payer":
    "The engine receives only whether the employing entity is Indonesian; the interface does not infer a visa from it.",
  "q.work_payer.opt.yes": "Yes, my employer is an Indonesian entity",
  "q.work_payer.opt.no": "No, I do not have an Indonesian employer",

  "q.work_indonesia_compensation":
    "Will any compensation for this activity come from an Indonesian source?",
  "q.work_indonesia_compensation.hint":
    "Answer about the source of payment, not the currency or bank account.",
  "why.work_indonesia_compensation":
    "This maps directly to the compensation-source fact; amount and eligibility are not inferred.",
  "q.work_sponsor_confirmed":
    "Has an Indonesian work sponsor confirmed they will support the process?",
  "q.work_sponsor_confirmed.hint":
    "A conversation or possible employer is not a confirmed sponsor.",
  "why.work_sponsor_confirmed":
    "The engine receives only your yes or no answer about sponsor confirmation.",

  "q.remote_clients": "Will you serve clients in Indonesia?",
  "q.remote_clients.hint":
    "Answer about the clients you serve. Your employer and payment source are separate questions.",
  "why.remote_clients":
    "The engine receives whether you serve Indonesian clients; it does not infer this from where you live.",
  "q.remote_clients.opt.foreign": "No, I will not serve clients in Indonesia",
  "q.remote_clients.opt.indonesian":
    "Yes, I only serve clients in Indonesia",
  "q.remote_clients.opt.mixed": "Yes, in Indonesia and abroad",

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
    "The engine receives the country code exactly as entered; the interface does not classify it.",
  "q.remote_pt_pma":
    "Is this remote-work plan tied to a committed Indonesian PT PMA?",
  "q.remote_pt_pma.hint":
    "Choose yes only for a real commitment, not a company you may form later.",
  "why.remote_pt_pma":
    "This maps directly to investment.pt_pma_committed and does not imply approval.",

  "q.investment_vehicle": "What is the concrete basis of your plan?",
  "q.investment_vehicle.hint":
    "This routes the next factual questions and is not sent to the engine.",
  "q.investment_vehicle.opt.pt_pma": "A committed Indonesian PT PMA",
  "q.investment_vehicle.opt.property": "A qualifying property arrangement",
  "q.investment_vehicle.opt.bank_deposit": "A bank deposit in my own name",
  "q.investment_vehicle.opt.merit": "Merit, talent, or public contribution",
  "q.investment_vehicle.opt.family": "A family-linked route",
  "q.investment_vehicle.opt.undecided": "I have not chosen a basis yet",
  "why.investment_vehicle":
    "This label only chooses which exact facts to ask next. It never chooses a visa path.",
  "q.investment_pt_pma": "Is the PT PMA commitment already concrete?",
  "q.investment_pt_pma.hint":
    "Answer no for an idea, early discussion, or uncommitted plan.",
  "why.investment_pt_pma":
    "The engine receives a boolean commitment fact, with no inferred amount or status.",
  "q.investment_capital_idr": "What investment capital is committed?",
  "q.investment_capital_idr.hint":
    "Enter the exact whole-rupiah amount you can support with evidence.",
  "q.investment_capital_idr.label": "Committed investment capital",
  "why.investment_capital_idr":
    "The amount is sent as a financial decision fact. No threshold is shown or inferred here.",
  "q.investment_paid_up_capital_idr":
    "How much paid-up capital is already documented?",
  "q.investment_paid_up_capital_idr.hint":
    "Enter a whole-rupiah amount; use Not sure rather than estimating.",
  "q.investment_paid_up_capital_idr.label": "Documented paid-up capital",
  "why.investment_paid_up_capital_idr":
    "The engine receives the exact amount separately from planned investment capital.",
  "q.investment_role": "What role would you hold in the company?",
  "q.investment_role.hint": "Choose the exact proposed-role description.",
  "q.investment_role.opt.SHAREHOLDER_DIRECTOR": "Shareholder and director",
  "q.investment_role.opt.SHAREHOLDER_COMMISSIONER":
    "Shareholder and commissioner",
  "q.investment_role.opt.EMPLOYEE": "Employee",
  "q.investment_role.opt.NO_OPERATIONAL_ROLE": "No operational role",
  "q.investment_role.opt.OTHER": "Another role",
  "why.investment_role":
    "The selected closed-enum value is sent unchanged to investment.proposed_role.",
  "q.unit.idr": "IDR",
  "q.unit.usd": "USD",
  "q.unit.usd_month": "USD per month",

  "q.family_relation": "How are you related to the proposed sponsor?",
  "q.family_relation.hint": "Describe your relationship to the sponsor. Child and parent cases currently need a review of the family relationship before a route can be recommended.",
  "q.family_relation.opt.SPOUSE": "I am the sponsor’s spouse",
  "q.family_relation.opt.CHILD": "I am the sponsor’s child",
  "q.family_relation.opt.PARENT": "I am the sponsor’s parent",
  "q.family_relation.opt.SIBLING": "I am the sponsor’s sibling",
  "q.family_relation.opt.DEPENDENT": "I am another dependent of the sponsor",
  "q.family_relation.opt.STEPCHILD": "I am the sponsor’s stepchild",
  "q.family_relation.opt.OTHER": "Another relationship",
  "why.family_relation":
    "Your relationship is recorded exactly as selected. For child and parent cases, an advisor must confirm who is applying and who is sponsoring before a route can be recommended.",
  "q.marital_status": "What is your current marital status?",
  "q.marital_status.hint": "Choose your current legal status.",
  "q.marital_status.opt.SINGLE": "Single",
  "q.marital_status.opt.MARRIED": "Married",
  "q.marital_status.opt.DIVORCED": "Divorced",
  "q.marital_status.opt.WIDOWED": "Widowed",
  "q.marital_status.opt.OTHER": "Another status",
  "why.marital_status":
    "The engine receives the closed-enum status exactly as selected.",
  "q.family_sponsor_nationalities":
    "Which nationalities appear on your sponsor’s passports?",
  "q.family_sponsor_nationalities.hint":
    "Choose each passport country. The answer stays separate from your own nationalities.",
  "q.family_sponsor_nationalities.label": "Sponsor passport countries",
  "why.family_sponsor_nationalities":
    "Sponsor nationality is a separate engine fact and is never copied from your own passports.",
  "q.family_sponsor_status_code":
    "What status code appears on your sponsor’s current permit?",
  "q.family_sponsor_status_code.hint":
    "Enter the printed product code, for example E31. Use Not sure if you cannot verify it.",
  "q.family_sponsor_status_code.label": "Sponsor permit code",
  "why.family_sponsor_status_code":
    "The code is sent exactly as typed. The interface does not translate a description into a permit code.",
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
    "The engine receives yes, no, or UNKNOWN; no registration status is inferred.",
  "q.family_stepchild_marriage_certificate_confirmed":
    "Can you provide the marriage certificate of your parent and their spouse in the Indonesian–foreign marriage?",
  "q.family_stepchild_marriage_certificate_confirmed.hint":
    "This is the marriage certificate for the mixed Indonesian–foreign marriage the stepchild relationship comes from.",
  "why.family_stepchild_marriage_certificate_confirmed":
    "The engine checks this evidence fact directly; it is not inferred from the marriage-registered answer above.",
  "q.family_stepchild_birth_certificate_confirmed":
    "Can you provide the stepchild's birth certificate?",
  "q.family_stepchild_birth_certificate_confirmed.hint":
    "The birth certificate should show the biological parent who is part of the mixed marriage.",
  "why.family_stepchild_birth_certificate_confirmed":
    "Birth-certificate evidence is sent as its own boolean decision fact.",
  "q.family_sponsor_confirmed":
    "Has your proposed sponsor confirmed they will support the process?",
  "q.family_sponsor_confirmed.hint":
    "Choose yes only after the sponsor has agreed.",
  "why.family_sponsor_confirmed":
    "Sponsor confirmation is sent as its own boolean decision fact.",

  "q.retirement_basis": "Which basis can you document today?",
  "q.retirement_basis.hint":
    "This only selects the next factual questions; it does not choose a visa.",
  "q.retirement_basis.opt.bank_deposit": "A bank deposit in my own name",
  "q.retirement_basis.opt.property": "A property arrangement",
  "q.retirement_basis.opt.passive_income": "Regular passive monthly income",
  "q.retirement_basis.opt.family_sponsor": "A confirmed sponsor",
  "q.retirement_basis.opt.undecided": "I have not chosen a basis",
  "why.retirement_basis":
    "There is no matching engine fact for this label. It only routes the next exact inputs.",
  "q.secondhome_basis": "Which Second Home basis can you document today?",
  "q.secondhome_basis.hint":
    "Pick the one you can evidence now. Use Not sure rather than guessing.",
  "q.secondhome_basis.opt.bank_deposit": "A bank deposit held in my own name",
  "q.secondhome_basis.opt.property": "A property arrangement",
  "why.secondhome_basis":
    "This only decides which evidence questions follow; the engine receives the evidence itself, never this label.",
  "q.secondhome_deposit_usd": "What bank deposit can you document?",
  "q.secondhome_deposit_usd.hint":
    "Enter the exact whole-dollar amount; use Not sure rather than estimating.",
  "q.secondhome_deposit_usd.label": "Documented bank deposit",
  "why.secondhome_deposit_usd":
    "The exact amount maps to secondhome.bank_deposit_usd; no threshold is shown here.",
  "q.secondhome_state_bank":
    "Is the deposit held at an Indonesian state-owned bank?",
  "q.secondhome_state_bank.hint": "Answer from the bank documentation.",
  "why.secondhome_state_bank":
    "This yes/no value is sent separately from the deposit amount.",
  "q.secondhome_own_name": "Is the full deposit held in your own name?",
  "q.secondhome_own_name.hint": "Do not combine accounts or account holders.",
  "why.secondhome_own_name":
    "This yes/no value is sent separately; the interface never assumes ownership.",
  "q.secondhome_property_value_usd":
    "What property value can you document for this plan?",
  "q.secondhome_property_value_usd.hint":
    "Enter the exact whole-dollar value supported by documents.",
  "q.secondhome_property_value_usd.label": "Documented property value",
  "why.secondhome_property_value_usd":
    "The engine receives the exact value; ownership and tenure are not inferred.",
  "q.secondhome_passive_income_usd":
    "What passive monthly income can you document?",
  "q.secondhome_passive_income_usd.hint":
    "Enter the exact whole-dollar monthly amount.",
  "q.secondhome_passive_income_usd.label": "Documented passive income",
  "why.secondhome_passive_income_usd":
    "The monthly amount maps directly to the engine fact and is never estimated from assets.",

  "q.study_level": "What level of study are you planning?",
  "q.study_level.hint": "Choose the level shown by the institution.",
  "q.study_level.opt.PRIMARY": "Primary school",
  "q.study_level.opt.SECONDARY": "Secondary school",
  "q.study_level.opt.VOCATIONAL": "Vocational programme",
  "q.study_level.opt.UNDERGRADUATE": "Undergraduate degree",
  "q.study_level.opt.POSTGRADUATE": "Postgraduate degree",
  "q.study_level.opt.RESEARCH": "Research",
  "q.study_level.opt.OTHER": "Another level",
  "why.study_level": "Study requirements depend on the programme level confirmed by your institution.",
  "q.study_admission_confirmed":
    "Has an Indonesian institution confirmed your admission?",
  "q.study_admission_confirmed.hint":
    "An application in progress is not confirmed admission.",
  "why.study_admission_confirmed":
    "Admission confirmation is sent as a separate yes/no fact.",
  "q.study_sponsor_confirmed":
    "Has the institution or study sponsor confirmed support?",
  "q.study_sponsor_confirmed.hint":
    "Choose yes only if the sponsor has agreed.",
  "why.study_sponsor_confirmed":
    "Sponsor confirmation is sent separately from admission.",

  "q.diaspora_connection": "What is your connection to Indonesia?",
  "q.diaspora_connection.hint":
    "This is human context only; nationality remains a separate exact fact.",
  "q.diaspora_connection.opt.former_wni": "I am a former Indonesian citizen",
  "q.diaspora_connection.opt.descendant":
    "I am a descendant of an Indonesian citizen",
  "q.diaspora_connection.opt.dual":
    "I may hold or have held more than one citizenship",
  "q.diaspora_connection.opt.family": "My connection is through family",
  "q.diaspora_connection.opt.other": "Another connection",
  "why.diaspora_connection":
    "The engine has no diaspora-connection fact. This answer is retained only for human context.",
  "q.diaspora_documents": "Can you document that connection?",
  "q.diaspora_documents.hint":
    "Do not upload documents here; answer only whether evidence exists.",
  "why.diaspora_documents":
    "This is human context only and cannot improve automated eligibility.",

  "q.other_purpose": "Which activity is closest to your plan?",
  "q.other_purpose.hint":
    "This context is not translated into an engine purpose or product code.",
  "q.other_purpose.opt.transit": "Transit",
  "q.other_purpose.opt.medical": "Medical treatment or support",
  "q.other_purpose.opt.volunteer": "Volunteer activity",
  "q.other_purpose.opt.religious": "Religious activity",
  "q.other_purpose.opt.arts_sport": "Arts or sport",
  "q.other_purpose.opt.journalism": "Journalism or media",
  "q.other_purpose.opt.crew": "Transport crew",
  "q.other_purpose.opt.other": "Something not listed",
  "why.other_purpose":
    "There is no one-to-one engine fact for these labels, so this remains human context.",
  "q.other_paid_activity": "Will any part of this activity be paid?",
  "q.other_paid_activity.hint":
    "This is human context only; it is not converted into an employment fact.",
  "why.other_paid_activity":
    "The engine has no exact matching fact for this broad question, so the answer cannot support a recommendation.",

  "q.stay_days": "How many days do you plan to stay?",
  "q.stay_days.hint":
    "Enter the planned total as a whole number; this is not a legal threshold.",
  "q.stay_days.label": "Planned stay",
  "q.stay_days.unit": "days",
  "why.stay_days":
    "The decision engine checks your exact planned duration instead of guessing from a broad range.",

  "q.review_gate": "A few honest questions before we show you anything",
  "q.review_gate.hint":
    "Any of these means a human reviews your case — never an automated verdict. That’s a feature, not a penalty.",
  "why.review_gate":
    "Only the separate immigration-history items map to an engine fact. Every other selection stays a review signal.",
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
    "You marked your current location as uncertain; no location was assumed.",
  "assumption.permit_expiry":
    "You weren’t sure when your current stay permission expires, so no deadline was inferred.",
  "assumption.stay_days":
    "You weren’t sure about the planned stay, so no duration was inferred.",
  "assumption.work_payer":
    "You weren’t sure whether your employer is an Indonesian entity; no employer status was assumed.",
  "assumption.remote_clients":
    "You weren’t sure whether you will serve clients in Indonesia; no client location was assumed.",
  "assumption.generic":
    "You marked “Not sure” for “{{question}}”; no value was inferred.",

  "whyweask.trigger": "Why we ask",
  "whyweask.trigger.aria": "Why we ask this question",
  "whyweask.fact_prefix": "Decision input: {{facts}}",
  "whyweask.review_only":
    "Review signal; only these listed facts can be transmitted: {{facts}}",
  "whyweask.human_context":
    "Human context only — not transmitted as an engine fact.",

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
  "tree.work_payer": "Employer registration",
  "tree.work_indonesia_compensation": "Payment source",
  "tree.work_sponsor_confirmed": "Work sponsor",
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

  "paths.counter.label": "{{count}} interview {{plural:branch|branches}}",
  "paths.counter.aria":
    "{{count}} interview {{plural:branch|branches}} remaining",

  "confirmation.title": "Here’s what you told us",
  "confirmation.your_answers": "Your answers",
  "confirmation.group.location": "Current situation",
  "confirmation.group.identity": "Identity facts",
  "confirmation.group.intent": "Your intent",
  "confirmation.group.details": "Branch details",
  "confirmation.group.review": "Review signals",
  "confirmation.assumptions_title": "Answers still uncertain",
  "confirmation.edit": "Edit",
  "confirmation.paths_remaining":
    "{{count}} interview {{plural:branch|branches}} remaining",
  "confirmation.price_preview":
    "If a supported Bali Zero service has verified pricing, it will appear as one all-inclusive amount.",
  "confirmation.cta": "See my options",

  "verdict.headline.SUPPORTED_CANDIDATES": "Supported paths found",
  "verdict.headline.HUMAN_REVIEW_REQUIRED":
    "This needs a human, not an algorithm",
  "verdict.headline.NO_SUPPORTED_PATH":
    "No supported path established",
  "verdict.headline.TEMPORARILY_UNAVAILABLE":
    "The verified decision service cannot complete this assessment",
  "verdict.headline.NEEDS_INPUT": "More information is needed",
  "verdict.evaluating": "Checking the verified rules…",
  "verdict.eligibility.eligible": "Eligible",
  "verdict.eligibility.likely": "Likely",
  "verdict.eligibility.conditional": "Conditional",
  "verdict.eligibility.likely-not": "Likely not",
  "verdict.state_description.SUPPORTED_CANDIDATES":
    "The deterministic engine supports the paths shown below for the facts and dated sources in this assessment.",
  "verdict.state_description.HUMAN_REVIEW_REQUIRED":
    "Nothing here is guessed. A Bali Zero advisor reviews cases like yours by hand.",
  "verdict.state_description.NO_SUPPORTED_PATH":
    "This engine has not established a supported route from these facts. This is not a universal finding of ineligibility. Review the reasons and your answers before deciding your next step.",
  "verdict.state_description.TEMPORARILY_UNAVAILABLE":
    "We’d rather say so plainly than fake a result.",
  "verdict.state_description.NEEDS_INPUT":
    "This assessment cannot establish a supported path until the missing details are resolved.",
  "verdict.provenance_headline.CLIENT_GUARD":
    "This assessment could not be verified",
  "verdict.provenance_headline.NETWORK_FAILURE":
    "We couldn’t reach the decision service",
  "verdict.provenance_headline.SHADOW": "Assessment verification in progress",
  "verdict.provenance_headline.PREVIEW": "Preview only — not a live decision",
  "verdict.provenance_description.CLIENT_GUARD":
    "No recommendation is shown. Review your answers or continue with a person.",
  "verdict.provenance_description.NETWORK_FAILURE":
    "No result was generated. Your answers were not replaced with a guess.",
  "verdict.provenance_description.SHADOW":
    "Your assessment was submitted for verification, but no visa path is shown while public enforcement is disabled.",
  "verdict.provenance_description.PREVIEW":
    "This screen is test data for product review and cannot support a recommendation.",

  "outcome.comparison_title": "How the paths compare",
  "outcome.comparison_col.visa": "Path",
  "outcome.comparison_col.eligibility": "Eligibility",
  "outcome.comparison_col.timeline": "Timeline",
  "outcome.comparison_col.price": "Price",
  "outcome.timeline_title": "Processing timeline",
  "outcome.timeline_range": "About {{min}}–{{max}} days",
  "outcome.price_label": "All-inclusive price",
  "outcome.price_all_inclusive": "One number — no PNBP-vs-fee split, ever.",
  "outcome.price_valid_until": "Quote valid until {{date}}",
  // Finding #17 (adversarial review 2026-07-17): "Free"/WhatsApp summary
  // header were hardcoded English/Indonesian ternaries in OutcomeSheet.tsx
  // instead of dict entries — invisible to the i18n parity test and to
  // anyone editing copy without reading the component source.
  "outcome.price_free": "Free",
  "outcome.whatsapp_summary_header": "Visa Oracle decision summary:",
  "outcome.checklist_title": "Operational document checklist",
  "outcome.next_steps_title": "Your next 3 steps",
  "outcome.next_steps.default.1":
    "Message a Bali Zero advisor with this summary",
  "outcome.next_steps.default.2": "Gather the documents listed above",
  "outcome.next_steps.default.3": "Confirm your timeline before booking travel",
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
  "outcome.business_catalog_title": "Another Business option to check",
  "outcome.d12_catalog_name": "Pre-investment visit — multiple entry",
  "outcome.d12_catalog_scope":
    "For pre-investment visits or exploring a new business, including site surveys and feasibility studies.",
  "outcome.d12_catalog_status": "Eligibility not yet established",
  "outcome.d12_catalog_assessment":
    "This assessment has not established your eligibility for D12. Check that your planned activities and documents meet its requirements.",
  "outcome.d12_catalog_source": "D12 requirements — Indonesian Immigration",
  "q.business_activity.opt.preinvestment": "Surveys or feasibility studies to start a business",
  "outcome.order_note": "Shown in the engine’s deterministic order. This is not a comparison of suitability or a recommendation of the best visa.",
  "outcome.d12_duration_title": "Stay, extensions and visa validity",
  "outcome.d12_duration": "D12 permits up to 180 days per arrival. A longer stay requires a separate extension; this assessment does not grant it. Visa validity is the period in which the visa can be used, not permission for an uninterrupted stay of that length. The processing estimate below is a different operational measure.",
  "outcome.conditions_title": "Conditions and checks still to satisfy",
  "outcome.conditions_note": "These are source-backed conditions, not verified applicant documents. This interview has not established that you meet every application requirement.",
  "outcome.other_context": "Other rule context",
  "outcome.source_reference": "Source {{number}}",
  "outcome.rank": "Result {{rank}}",
  "outcome.axis.legal": "Legal eligibility",
  "outcome.axis.operational": "Operational availability",
  "outcome.axis.service": "Bali Zero service",
  "outcome.status.SUPPORTED": "Supported",
  "outcome.status.CONDITIONAL": "Conditional",
  "outcome.status.NOT_SUPPORTED": "Not supported",
  "outcome.status.UNKNOWN": "Unknown",
  "outcome.status.AVAILABLE": "Available",
  "outcome.status.TEMPORARILY_UNAVAILABLE": "Temporarily unavailable",
  "outcome.status.CONTACT_REQUIRED": "Contact required",
  "outcome.status.NOT_OFFERED": "Not offered",
  "outcome.why_supported": "Facts used by the matching rules",
  "outcome.timeline_dates": "{{from}} to {{to}}",
  "outcome.timeline_basis": "Calculated from the assessment date: {{date}}",
  "outcome.timeline_unavailable":
    "Timeline unavailable — no verified calendar estimate",
  "outcome.timeline_contact_required":
    "Timeline needs operational confirmation",
  "outcome.documents_unknown": "Operational checklist unavailable",
  "outcome.documents_contact": "Source conditions above remain relevant. A verified checklist for preparing and submitting your particular application is not available from this assessment.",
  "outcome.document_status.CONDITIONAL": "Conditional",
  "outcome.document_status.UNKNOWN": "To be confirmed",
  "outcome.needs_input_body":
    "The engine abstained because these facts are still missing:",
  "outcome.needs_input_advisor_body":
    "The remaining details cannot be collected through an additional question in this interview. A Bali Zero advisor can review the missing information with you. You can also edit your recorded answers below; no supported path has been established.",
  "outcome.answer_missing_input": "Answer this",
  "outcome.retryable": "You can safely try this evaluation again.",
  "outcome.not_retryable": "A person needs to check this before you continue.",
  "outcome.sources_title": "Evidence returned with this assessment",
  "outcome.source_dates": "Recorded applicability from {{effective}} · source checked {{observed}}",
  "outcome.freshness.CURRENT": "Current at assessment time",
  "outcome.freshness.STALE": "Stale — review required",
  "outcome.freshness.UNKNOWN": "Freshness unknown",
  "outcome.assessment_dates":
    "Effective {{effective}} · observed {{observed}} · evaluated {{evaluated}}",
  "outcome.provenance.CLIENT_GUARD.title": "Client safety hold",
  "outcome.provenance.CLIENT_GUARD.body":
    "This is an operational hold. The assessment could not be verified for display; no visa path is shown.",
  "outcome.provenance.NETWORK_FAILURE.title": "Decision service unavailable",
  "outcome.provenance.NETWORK_FAILURE.body":
    "The engine did not answer. No fallback result or candidate was fabricated.",
  "outcome.provenance.SHADOW.title": "Verification mode",
  "outcome.provenance.SHADOW.body":
    "The assessment is measured in shadow mode. No engine candidate is exposed, ranked, or replaced with a preview.",
  "outcome.provenance.PREVIEW.title": "Preview data",
  "outcome.provenance.PREVIEW.body":
    "This content exists only for testing the interface and is not a recommendation.",
  "outcome.assumptions_receipt_title": "Assumptions & caveats, dated",
  "outcome.assumptions_receipt_empty":
    "This assessment records no assumptions. Missing or uncertain information may still limit the result.",
  "outcome.freshness_stamp": "Decision ruleset evaluated {{date}}",
  "outcome.disclaimer.not_government":
    "This is a private decision-support tool, not a government service.",
  "outcome.disclaimer.based_on_facts":
    "The result reflects only the facts you entered and the dated sources shown above.",
  "outcome.disclaimer.not_approval":
    "It is not an approval, a guarantee, or a filing.",
  "outcome.disclaimer.complex_to_human":
    "Complex or flagged cases always go to a human — Ditjen Imigrasi decides, not this tool.",
  "outcome.alternatives_title": "Three paths worth a look instead",
  "outcome.alternatives_intro":
    "None of these are a downgrade — they’re simply what fits.",
  "outcome.no_path_body":
    "The combination you described does not match a path supported by the verified decision rules.",
  "outcome.no_path_reasons_title": "Reasons from the route assessment",
  "outcome.no_path_reasons_context": "The engine assesses several visa products. These reasons may concern different products; they are not a combined checklist for one visa. Where a reason does not name a visa, this response does not identify its product.",
  "outcome.temporarily_unavailable_body":
    "The decision service cannot verify this case right now. No fallback path has been fabricated.",
  "outcome.human_review_body":
    "Your case needs a person’s judgment — nothing here was guessed on your behalf.",
  "outcome.overstay_reassurance":
    "Overstay is fixable. It is not the end of your story here.",

  "prototype.badge": "Visa decision support",
  "prototype.badge.detail":
    "Only deterministic engine outcomes may appear as supported paths.",

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
} as const;

type Keys = keyof typeof en;

const id: Record<Keys, string> = {
  "framing.title": "Peta, bukan permohonan",
  "framing.body":
    "Jawab dengan jujur, termasuk “Saya tidak tahu.” Tidak ada yang diajukan di sini, dan antarmuka tidak pernah memilih jalur visa sendiri.",
  "framing.cta": "Mulai",

  "q.in_indonesia": "Apakah Anda sedang berada di Indonesia sekarang?",
  "q.in_indonesia.hint":
    "Ini menentukan pertanyaan mana yang relevan selanjutnya.",
  "q.in_indonesia.opt.yes": "Ya, saya di sini",
  "q.in_indonesia.opt.no": "Belum, saya sedang merencanakan",
  "why.in_indonesia":
    "Lokasi Anda saat ini memberi tahu mesin apakah ini situasi onshore atau rencana mendatang.",

  "q.permit_expiry": "Kapan izin tinggal Anda saat ini berakhir?",
  "q.permit_expiry.hint":
    "Tanggal pada visa atau ITAS/KITAS Anda — bukan paspor.",
  "q.permit_expiry.label": "Tanggal berakhir",
  "why.permit_expiry":
    "Mesin membutuhkan tanggalnya untuk menilai waktu; antarmuka tidak menyimpulkan jalur pengajuan darinya.",
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
    "Mesin menerima kode status yang tercetak tanpa perubahan; antarmuka tidak pernah menebaknya dari nama izin.",
  "q.holds_stay_permit":
    "Apakah Anda saat ini memegang izin tinggal terbatas atau tetap (KITAS / KITAP)?",
  "why.holds_stay_permit":
    "Jawaban ini menentukan pertanyaan izin berikutnya. Jika Anda menjawab Tidak dan tidak ada kode status tercetak yang dikumpulkan, mesin mencatat bahwa Anda tidak memiliki izin tinggal. Jawaban Ya tetap memerlukan kode persis dan tidak menetapkan jenis izin.",
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
    "Mesin menerima kode yang tercetak tanpa perubahan, sama seperti daftar kode di atas — antarmuka tidak pernah menebaknya dari nama izin.",

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
    "Jumlah hari overstay aktif adalah fakta safety-critical terpisah. Nilai ini tidak pernah dihitung dari tanggal berakhir di browser.",
  "q.wants_onshore_conversion":
    "Apakah Anda ingin mengubah status tanpa meninggalkan Indonesia?",
  "q.wants_onshore_conversion.hint":
    "Jawab tentang proses yang Anda inginkan, bukan apakah proses itu akan disetujui.",
  "q.wants_onshore_conversion.offshore":
    "Setelah berada di Indonesia, apakah Anda berencana beralih ke izin lain tanpa meninggalkan Indonesia?",
  "q.wants_onshore_conversion.offshore.hint":
    "Jawab tentang proses yang Anda rencanakan setelah tiba, bukan apakah proses itu akan disetujui.",
  "why.wants_onshore_conversion":
    "Fakta proses ya atau tidak ini dikirim tanpa memilih jalur konversi.",
  "q.application_channel":
    "Kanal permohonan mana yang benar-benar Anda jalani?",
  "q.application_channel.hint":
    "Pilih hanya kanal yang sudah dikonfirmasi untuk kasus Anda, atau pilih Tidak yakin.",
  "q.application_channel.opt.OFFSHORE":
    "Mengajukan setelah meninggalkan Indonesia",
  "q.application_channel.opt.ONSHORE_CONVERSION": "Konversi status onshore",
  "q.application_channel.opt.STATUS_BRIDGING": "Proses status bridging",
  "why.application_channel":
    "Kanal enum tertutup yang dipilih dikirim tanpa perubahan. Antarmuka tidak menetapkan kanal dari tanggal Anda.",
  "q.application_channel.conflict":
    "Kanal ini tidak sesuai dengan jawaban Anda sebelumnya tentang mengubah status tanpa meninggalkan Indonesia. Kembali dan perbaiki salah satu dari kedua jawaban — kami tidak akan menebak mana yang benar.",

  "q.nationalities": "Kewarganegaraan apa yang tercantum di paspor Anda?",
  "q.nationalities.hint":
    "Pilih setiap negara paspor. Jawaban tersimpan tetap berupa kode negara yang tidak bergantung pada bahasa.",
  "q.nationalities.label": "Negara paspor",
  "why.nationalities":
    "Kewarganegaraan diperiksa sebagai fakta keputusan yang tepat. Beberapa kewarganegaraan tetap terpisah dan tidak ditebak.",
  "q.birth_date": "Kapan tanggal lahir Anda?",
  "q.birth_date.hint":
    "Tanggal dikirim sebagai fakta keputusan; mesin menghitung usia secara konsisten.",
  "q.birth_date.label": "Tanggal lahir",
  "why.birth_date":
    "Beberapa jalur membedakan orang dewasa dan anak. Antarmuka tidak menghitung kelayakan dari usia Anda.",

  "lane.expired.notice":
    "Izin tinggal Anda sudah berakhir. Overstay bisa diselesaikan. Ini bukan akhir cerita Anda di sini — kasus ini selalu ditangani manusia, dan kami tidak akan menampilkan angka yang menakutkan di layar ini.",
  "lane.urgent.notice":
    "Waktu Anda tinggal 1–2 hari. Ini terlalu mepet untuk penelusuran otomatis — konsultan Bali Zero perlu melihat kasus ini hari ini.",
  "lane.bridging.notice":
    "Tanggal yang Anda masukkan tinggal tujuh hari atau kurang. Mesin dapat menahan keputusan untuk tinjauan manusia; antarmuka tidak memilih jalur bridging atau konversi.",
  "lane.extend.notice":
    "Anda masih punya waktu untuk membandingkan Extend dan Convert.",
  "lane.planning.notice":
    "Waktu masih longgar — ini perencanaan, bukan hal mendesak.",

  "q.category": "Apa tujuan Anda ke Indonesia?",
  "q.category.hint":
    "Pilih yang paling mendekati — bisa diperjelas berikutnya.",
  "why.category":
    "Ini hanya cabang wawancara awal. Hanya mesin yang dapat memutuskan apakah suatu jalur visa didukung.",
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
    "Tujuan yang tumpang tindih membutuhkan konteks manusia. Jawaban ini tidak diterjemahkan menjadi fakta mesin.",
  "q.entry_pattern": "Bagaimana Anda berencana masuk ke Indonesia?",
  "q.entry_pattern.hint": "Pilih pola yang benar-benar Anda rencanakan.",
  "q.entry_pattern.opt.SINGLE": "Satu kali masuk",
  "q.entry_pattern.opt.MULTIPLE": "Lebih dari satu kali masuk",
  "why.entry_pattern":
    "Mesin menerima SINGLE atau MULTIPLE persis seperti pilihan Anda.",

  "q.sponsor_category":
    "Siapa yang mensponsori masa tinggal Anda di Indonesia?",
  "q.sponsor_category.hint":
    "Pilih pihak yang menyediakan atau menjamin izin Anda, bukan yang membiayai kebutuhan sehari-hari Anda.",
  "q.sponsor_category.opt.NONE":
    "Saya tidak memiliki sponsor",
  "q.sponsor_category.opt.INDIVIDUAL":
    "Perorangan (sponsor keluarga atau pribadi)",
  "q.sponsor_category.opt.EMPLOYER": "Pemberi kerja — perusahaan di Indonesia",
  "q.sponsor_category.opt.EDUCATION": "Institusi pendidikan",
  "q.sponsor_category.opt.INVESTMENT": "Investasi atau perusahaan milik saya",
  "q.sponsor_category.opt.GOVERNMENT": "Instansi pemerintah",
  "why.sponsor_category":
    "Beberapa jalur memerlukan jenis sponsor tertentu. Jawaban ini mengidentifikasi sponsor, bukan memastikan bahwa Anda memenuhi syarat.",

  "q.business_activity": "Apa kegiatan utama Anda dalam perjalanan bisnis?",
  "q.business_activity.hint": "Jelaskan kegiatan Anda. Survei dan studi kelayakan untuk memulai usaha berbeda dari kunjungan komersial biasa. Pelatihan, pekerjaan operasional, dan kegiatan yang belum pasti perlu ditinjau.",
  "q.business_activity.opt.meetings": "Pertemuan komersial atau kunjungan pelanggan/lokasi",
  "q.business_activity.opt.negotiation": "Negosiasi atau penandatanganan",
  "q.business_activity.opt.conference": "Menghadiri konferensi atau pameran sebagai peserta",
  "q.business_activity.opt.training": "Memberi atau menerima pelatihan",
  "q.business_activity.opt.other": "Kegiatan bisnis lainnya",
  "why.business_activity": "Penjajakan prainvestasi dikirim sebagai tujuan investasi. Kegiatan lain tetap bertujuan bisnis; pertemuan biasa, negosiasi, konferensi, pelatihan, dan kegiatan yang tidak spesifik perlu ditinjau karena kategori kegiatan saat ini belum dapat membedakan semua cakupan visa dengan aman.",

  "q.work_payer":
    "Apakah entitas pemberi kerja Anda terdaftar di Indonesia?",
  "q.work_payer.hint":
    "Jawab tentang pemberi kerja resmi Anda, bukan asal pembayaran. Kompensasi ditanyakan secara terpisah.",
  "why.work_payer":
    "Mesin hanya menerima apakah entitas pemberi kerja merupakan entitas Indonesia; antarmuka tidak menyimpulkan visa darinya.",
  "q.work_payer.opt.yes": "Ya, pemberi kerja saya merupakan entitas Indonesia",
  "q.work_payer.opt.no": "Tidak, saya tidak memiliki pemberi kerja Indonesia",

  "q.work_indonesia_compensation":
    "Apakah ada kompensasi untuk kegiatan ini yang berasal dari sumber Indonesia?",
  "q.work_indonesia_compensation.hint":
    "Jawab tentang sumber pembayaran, bukan mata uang atau rekening bank.",
  "why.work_indonesia_compensation":
    "Ini dipetakan langsung ke fakta sumber kompensasi; jumlah dan kelayakan tidak disimpulkan.",
  "q.work_sponsor_confirmed":
    "Apakah sponsor kerja Indonesia sudah mengonfirmasi dukungan proses?",
  "q.work_sponsor_confirmed.hint":
    "Percakapan atau calon pemberi kerja belum berarti sponsor sudah dikonfirmasi.",
  "why.work_sponsor_confirmed":
    "Mesin hanya menerima jawaban ya atau tidak tentang konfirmasi sponsor.",

  "q.remote_clients": "Apakah Anda akan melayani klien di Indonesia?",
  "q.remote_clients.hint":
    "Jawab tentang klien yang Anda layani. Pemberi kerja dan sumber pembayaran ditanyakan secara terpisah.",
  "why.remote_clients":
    "Mesin menerima apakah Anda melayani klien Indonesia; hal ini tidak disimpulkan dari tempat tinggal Anda.",
  "q.remote_clients.opt.foreign":
    "Tidak, saya tidak akan melayani klien di Indonesia",
  "q.remote_clients.opt.indonesian":
    "Ya, saya hanya melayani klien di Indonesia",
  "q.remote_clients.opt.mixed": "Ya, di Indonesia dan di luar negeri",

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
    "Mesin menerima kode negara persis seperti yang dimasukkan; antarmuka tidak mengklasifikasikannya.",
  "q.remote_pt_pma":
    "Apakah rencana kerja remote ini terikat pada komitmen PT PMA Indonesia?",
  "q.remote_pt_pma.hint":
    "Pilih ya hanya untuk komitmen nyata, bukan perusahaan yang mungkin dibentuk nanti.",
  "why.remote_pt_pma":
    "Ini dipetakan langsung ke investment.pt_pma_committed dan tidak menyiratkan persetujuan.",

  "q.investment_vehicle": "Apa dasar konkret rencana Anda?",
  "q.investment_vehicle.hint":
    "Ini hanya mengarahkan pertanyaan faktual berikutnya dan tidak dikirim ke mesin.",
  "q.investment_vehicle.opt.pt_pma": "Komitmen PT PMA Indonesia",
  "q.investment_vehicle.opt.property": "Pengaturan properti",
  "q.investment_vehicle.opt.bank_deposit": "Deposito bank atas nama saya",
  "q.investment_vehicle.opt.merit": "Prestasi, talenta, atau kontribusi publik",
  "q.investment_vehicle.opt.family": "Jalur terkait keluarga",
  "q.investment_vehicle.opt.undecided": "Saya belum memilih dasar",
  "why.investment_vehicle":
    "Label ini hanya menentukan fakta persis yang ditanyakan berikutnya. Label ini tidak pernah memilih jalur visa.",
  "q.investment_pt_pma": "Apakah komitmen PT PMA sudah konkret?",
  "q.investment_pt_pma.hint":
    "Jawab tidak untuk ide, pembicaraan awal, atau rencana tanpa komitmen.",
  "why.investment_pt_pma":
    "Mesin menerima fakta komitmen boolean, tanpa menyimpulkan jumlah atau status.",
  "q.investment_capital_idr":
    "Berapa modal investasi yang sudah dikomitmenkan?",
  "q.investment_capital_idr.hint":
    "Masukkan jumlah rupiah bulat yang dapat didukung bukti.",
  "q.investment_capital_idr.label": "Modal investasi yang dikomitmenkan",
  "why.investment_capital_idr":
    "Jumlah dikirim sebagai fakta keputusan finansial. Tidak ada ambang yang ditampilkan atau disimpulkan di sini.",
  "q.investment_paid_up_capital_idr":
    "Berapa modal disetor yang sudah terdokumentasi?",
  "q.investment_paid_up_capital_idr.hint":
    "Masukkan jumlah rupiah bulat; pilih Tidak yakin daripada memperkirakan.",
  "q.investment_paid_up_capital_idr.label": "Modal disetor terdokumentasi",
  "why.investment_paid_up_capital_idr":
    "Mesin menerima jumlah persis, terpisah dari modal investasi yang direncanakan.",
  "q.investment_role": "Peran apa yang akan Anda pegang di perusahaan?",
  "q.investment_role.hint": "Pilih deskripsi peran yang tepat.",
  "q.investment_role.opt.SHAREHOLDER_DIRECTOR": "Pemegang saham dan direktur",
  "q.investment_role.opt.SHAREHOLDER_COMMISSIONER":
    "Pemegang saham dan komisaris",
  "q.investment_role.opt.EMPLOYEE": "Karyawan",
  "q.investment_role.opt.NO_OPERATIONAL_ROLE": "Tanpa peran operasional",
  "q.investment_role.opt.OTHER": "Peran lain",
  "why.investment_role":
    "Nilai enum tertutup yang dipilih dikirim tanpa perubahan ke investment.proposed_role.",
  "q.unit.idr": "IDR",
  "q.unit.usd": "USD",
  "q.unit.usd_month": "USD per bulan",

  "q.family_relation": "Apa hubungan Anda dengan calon sponsor?",
  "q.family_relation.hint": "Jelaskan hubungan Anda dengan sponsor. Kasus anak dan orang tua saat ini memerlukan tinjauan hubungan keluarga sebelum jalur dapat direkomendasikan.",
  "q.family_relation.opt.SPOUSE": "Saya adalah suami atau istri sponsor",
  "q.family_relation.opt.CHILD": "Saya adalah anak sponsor",
  "q.family_relation.opt.PARENT": "Saya adalah orang tua sponsor",
  "q.family_relation.opt.SIBLING": "Saya adalah saudara kandung sponsor",
  "q.family_relation.opt.DEPENDENT": "Saya adalah tanggungan lain sponsor",
  "q.family_relation.opt.STEPCHILD": "Saya adalah anak tiri sponsor",
  "q.family_relation.opt.OTHER": "Hubungan lain",
  "why.family_relation":
    "Hubungan Anda dicatat sesuai pilihan. Untuk kasus anak dan orang tua, penasihat harus memastikan siapa pemohon dan siapa sponsor sebelum jalur dapat direkomendasikan.",
  "q.marital_status": "Apa status perkawinan Anda saat ini?",
  "q.marital_status.hint": "Pilih status hukum Anda saat ini.",
  "q.marital_status.opt.SINGLE": "Belum menikah",
  "q.marital_status.opt.MARRIED": "Menikah",
  "q.marital_status.opt.DIVORCED": "Bercerai",
  "q.marital_status.opt.WIDOWED": "Duda atau janda",
  "q.marital_status.opt.OTHER": "Status lain",
  "why.marital_status":
    "Mesin menerima status enum tertutup persis seperti yang dipilih.",
  "q.family_sponsor_nationalities":
    "Kewarganegaraan apa yang tercantum di paspor sponsor Anda?",
  "q.family_sponsor_nationalities.hint":
    "Pilih setiap negara paspor. Jawaban tetap terpisah dari kewarganegaraan Anda.",
  "q.family_sponsor_nationalities.label": "Negara paspor sponsor",
  "why.family_sponsor_nationalities":
    "Kewarganegaraan sponsor adalah fakta mesin terpisah dan tidak pernah disalin dari paspor Anda.",
  "q.family_sponsor_status_code":
    "Kode status apa yang tercantum pada izin sponsor saat ini?",
  "q.family_sponsor_status_code.hint":
    "Masukkan kode produk yang tercetak, misalnya E31. Pilih Tidak yakin jika tidak dapat memverifikasinya.",
  "q.family_sponsor_status_code.label": "Kode izin sponsor",
  "why.family_sponsor_status_code":
    "Kode dikirim persis seperti yang diketik. Antarmuka tidak menerjemahkan deskripsi menjadi kode izin.",
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
    "Mesin menerima ya, tidak, atau UNKNOWN; status pencatatan tidak disimpulkan.",
  "q.family_stepchild_marriage_certificate_confirmed":
    "Dapatkah Anda memberikan akta nikah orang tua Anda dan pasangannya dalam pernikahan WNI–WNA tersebut?",
  "q.family_stepchild_marriage_certificate_confirmed.hint":
    "Ini adalah akta nikah untuk pernikahan campuran WNI-WNA yang menjadi dasar hubungan anak tiri.",
  "why.family_stepchild_marriage_certificate_confirmed":
    "Mesin memeriksa fakta bukti ini secara langsung; tidak disimpulkan dari jawaban pernikahan tercatat di atas.",
  "q.family_stepchild_birth_certificate_confirmed":
    "Dapatkah Anda memberikan akta lahir anak tiri?",
  "q.family_stepchild_birth_certificate_confirmed.hint":
    "Akta lahir sebaiknya menunjukkan orang tua kandung yang merupakan bagian dari pernikahan campuran.",
  "why.family_stepchild_birth_certificate_confirmed":
    "Bukti akta lahir dikirim sebagai fakta keputusan boolean tersendiri.",
  "q.family_sponsor_confirmed":
    "Apakah calon sponsor Anda sudah mengonfirmasi dukungan proses?",
  "q.family_sponsor_confirmed.hint":
    "Pilih ya hanya setelah sponsor menyetujuinya.",
  "why.family_sponsor_confirmed":
    "Konfirmasi sponsor dikirim sebagai fakta keputusan boolean tersendiri.",

  "q.retirement_basis": "Dasar mana yang dapat Anda buktikan saat ini?",
  "q.retirement_basis.hint":
    "Ini hanya memilih pertanyaan faktual berikutnya; bukan memilih visa.",
  "q.retirement_basis.opt.bank_deposit": "Deposito bank atas nama saya",
  "q.retirement_basis.opt.property": "Pengaturan properti",
  "q.retirement_basis.opt.passive_income": "Penghasilan pasif bulanan tetap",
  "q.retirement_basis.opt.family_sponsor": "Sponsor yang telah mengonfirmasi dukungan",
  "q.retirement_basis.opt.undecided": "Saya belum memilih dasar",
  "why.retirement_basis":
    "Tidak ada fakta mesin yang cocok untuk label ini. Label hanya mengarahkan input persis berikutnya.",
  "q.secondhome_basis":
    "Dasar Second Home mana yang dapat Anda buktikan saat ini?",
  "q.secondhome_basis.hint":
    "Pilih yang buktinya sudah Anda miliki sekarang. Gunakan Tidak yakin daripada menebak.",
  "q.secondhome_basis.opt.bank_deposit": "Deposito bank atas nama saya",
  "q.secondhome_basis.opt.property": "Pengaturan properti",
  "why.secondhome_basis":
    "Ini hanya menentukan pertanyaan bukti berikutnya; mesin menerima buktinya sendiri, bukan label ini.",
  "q.secondhome_deposit_usd": "Berapa deposito bank yang dapat Anda buktikan?",
  "q.secondhome_deposit_usd.hint":
    "Masukkan jumlah dolar bulat yang tepat; pilih Tidak yakin daripada memperkirakan.",
  "q.secondhome_deposit_usd.label": "Deposito bank terdokumentasi",
  "why.secondhome_deposit_usd":
    "Jumlah persis dipetakan ke secondhome.bank_deposit_usd; tidak ada ambang yang ditampilkan di sini.",
  "q.secondhome_state_bank": "Apakah deposito berada di bank BUMN Indonesia?",
  "q.secondhome_state_bank.hint": "Jawab berdasarkan dokumen bank.",
  "why.secondhome_state_bank":
    "Nilai ya atau tidak ini dikirim terpisah dari jumlah deposito.",
  "q.secondhome_own_name": "Apakah seluruh deposito atas nama Anda sendiri?",
  "q.secondhome_own_name.hint":
    "Jangan gabungkan rekening atau pemilik rekening.",
  "why.secondhome_own_name":
    "Nilai ya atau tidak ini dikirim terpisah; antarmuka tidak pernah mengasumsikan kepemilikan.",
  "q.secondhome_property_value_usd":
    "Berapa nilai properti yang dapat Anda buktikan untuk rencana ini?",
  "q.secondhome_property_value_usd.hint":
    "Masukkan nilai dolar bulat yang didukung dokumen.",
  "q.secondhome_property_value_usd.label": "Nilai properti terdokumentasi",
  "why.secondhome_property_value_usd":
    "Mesin menerima nilai persis. Kepemilikan dan bentuk penguasaan tidak disimpulkan dari izin tinggal.",
  "q.secondhome_passive_income_usd":
    "Berapa penghasilan pasif bulanan yang dapat Anda buktikan?",
  "q.secondhome_passive_income_usd.hint":
    "Masukkan jumlah bulanan dolar bulat yang tepat.",
  "q.secondhome_passive_income_usd.label": "Penghasilan pasif terdokumentasi",
  "why.secondhome_passive_income_usd":
    "Jumlah bulanan dipetakan langsung ke fakta mesin dan tidak pernah diperkirakan dari aset.",

  "q.study_level": "Tingkat studi apa yang Anda rencanakan?",
  "q.study_level.hint": "Pilih tingkat yang ditunjukkan oleh institusi.",
  "q.study_level.opt.PRIMARY": "Sekolah dasar",
  "q.study_level.opt.SECONDARY": "Sekolah menengah",
  "q.study_level.opt.VOCATIONAL": "Program vokasi",
  "q.study_level.opt.UNDERGRADUATE": "Sarjana",
  "q.study_level.opt.POSTGRADUATE": "Pascasarjana",
  "q.study_level.opt.RESEARCH": "Riset",
  "q.study_level.opt.OTHER": "Tingkat lain",
  "why.study_level": "Persyaratan studi bergantung pada tingkat program yang dikonfirmasi oleh institusi Anda.",
  "q.study_admission_confirmed":
    "Apakah institusi Indonesia sudah mengonfirmasi penerimaan Anda?",
  "q.study_admission_confirmed.hint":
    "Permohonan yang masih diproses belum berarti penerimaan terkonfirmasi.",
  "why.study_admission_confirmed":
    "Konfirmasi penerimaan dikirim sebagai fakta ya atau tidak tersendiri.",
  "q.study_sponsor_confirmed":
    "Apakah institusi atau sponsor studi sudah mengonfirmasi dukungan?",
  "q.study_sponsor_confirmed.hint":
    "Pilih ya hanya jika sponsor sudah menyetujui.",
  "why.study_sponsor_confirmed":
    "Konfirmasi sponsor dikirim terpisah dari penerimaan.",

  "q.diaspora_connection": "Apa hubungan Anda dengan Indonesia?",
  "q.diaspora_connection.hint":
    "Ini hanya konteks manusia; kewarganegaraan tetap menjadi fakta persis terpisah.",
  "q.diaspora_connection.opt.former_wni": "Saya mantan warga negara Indonesia",
  "q.diaspora_connection.opt.descendant":
    "Saya keturunan warga negara Indonesia",
  "q.diaspora_connection.opt.dual":
    "Saya mungkin memiliki atau pernah memiliki lebih dari satu kewarganegaraan",
  "q.diaspora_connection.opt.family": "Hubungan saya melalui keluarga",
  "q.diaspora_connection.opt.other": "Hubungan lain",
  "why.diaspora_connection":
    "Mesin tidak memiliki fakta hubungan diaspora. Jawaban ini hanya disimpan sebagai konteks manusia.",
  "q.diaspora_documents": "Apakah Anda dapat membuktikan hubungan tersebut?",
  "q.diaspora_documents.hint":
    "Jangan unggah dokumen di sini; jawab hanya apakah bukti tersedia.",
  "why.diaspora_documents":
    "Ini hanya konteks manusia dan tidak dapat meningkatkan kelayakan otomatis.",

  "q.other_purpose": "Kegiatan mana yang paling dekat dengan rencana Anda?",
  "q.other_purpose.hint":
    "Konteks ini tidak diterjemahkan menjadi tujuan mesin atau kode produk.",
  "q.other_purpose.opt.transit": "Transit",
  "q.other_purpose.opt.medical": "Perawatan atau pendampingan medis",
  "q.other_purpose.opt.volunteer": "Kegiatan sukarela",
  "q.other_purpose.opt.religious": "Kegiatan keagamaan",
  "q.other_purpose.opt.arts_sport": "Seni atau olahraga",
  "q.other_purpose.opt.journalism": "Jurnalistik atau media",
  "q.other_purpose.opt.crew": "Awak transportasi",
  "q.other_purpose.opt.other": "Hal lain yang tidak tercantum",
  "why.other_purpose":
    "Tidak ada fakta mesin satu-ke-satu untuk label ini, sehingga tetap menjadi konteks manusia.",
  "q.other_paid_activity": "Apakah ada bagian kegiatan ini yang dibayar?",
  "q.other_paid_activity.hint":
    "Ini hanya konteks manusia; tidak dikonversi menjadi fakta ketenagakerjaan.",
  "why.other_paid_activity":
    "Mesin tidak memiliki fakta persis untuk pertanyaan luas ini, sehingga jawabannya tidak dapat mendukung rekomendasi.",

  "q.stay_days": "Berapa hari Anda berencana tinggal?",
  "q.stay_days.hint":
    "Masukkan jumlah hari penuh yang direncanakan; angka ini bukan ambang hukum.",
  "q.stay_days.label": "Rencana masa tinggal",
  "q.stay_days.unit": "hari",
  "why.stay_days":
    "Mesin keputusan memeriksa durasi persis yang Anda rencanakan tanpa menebak dari rentang yang luas.",

  "q.review_gate": "Beberapa pertanyaan jujur sebelum kami tunjukkan hasilnya",
  "q.review_gate.hint":
    "Salah satu dari ini berarti kasus Anda ditinjau manusia — bukan keputusan otomatis. Ini fitur, bukan hukuman.",
  "why.review_gate":
    "Hanya item riwayat keimigrasian yang terpisah yang dipetakan ke fakta mesin. Pilihan lainnya tetap menjadi sinyal tinjauan.",
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
    "Anda menandai lokasi saat ini sebagai belum pasti; tidak ada lokasi yang diasumsikan.",
  "assumption.permit_expiry":
    "Anda belum yakin kapan izin tinggal saat ini berakhir, jadi tidak ada tenggat yang diperkirakan.",
  "assumption.stay_days":
    "Anda belum yakin tentang rencana masa tinggal, jadi tidak ada durasi yang diperkirakan.",
  "assumption.work_payer":
    "Anda belum yakin apakah pemberi kerja Anda merupakan entitas Indonesia; tidak ada status pemberi kerja yang diasumsikan.",
  "assumption.remote_clients":
    "Anda belum yakin apakah akan melayani klien di Indonesia; tidak ada lokasi klien yang diasumsikan.",
  "assumption.generic":
    "Anda memilih “Tidak yakin” untuk “{{question}}”; tidak ada nilai yang diperkirakan.",

  "whyweask.trigger": "Mengapa kami tanyakan ini",
  "whyweask.trigger.aria": "Mengapa kami menanyakan pertanyaan ini",
  "whyweask.fact_prefix": "Input keputusan: {{facts}}",
  "whyweask.review_only":
    "Sinyal tinjauan; hanya fakta yang tercantum ini yang dapat dikirim: {{facts}}",
  "whyweask.human_context":
    "Hanya konteks manusia — tidak dikirim sebagai fakta mesin.",

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
  "tree.work_payer": "Pendaftaran pemberi kerja",
  "tree.work_indonesia_compensation": "Sumber pembayaran",
  "tree.work_sponsor_confirmed": "Sponsor kerja",
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

  "paths.counter.label": "{{count}} cabang wawancara",
  "paths.counter.aria": "{{count}} cabang wawancara tersisa",

  "confirmation.title": "Berikut yang Anda sampaikan",
  "confirmation.your_answers": "Jawaban Anda",
  "confirmation.group.location": "Situasi saat ini",
  "confirmation.group.identity": "Fakta identitas",
  "confirmation.group.intent": "Tujuan Anda",
  "confirmation.group.details": "Rincian cabang",
  "confirmation.group.review": "Sinyal tinjauan",
  "confirmation.assumptions_title": "Jawaban yang belum pasti",
  "confirmation.edit": "Ubah",
  "confirmation.paths_remaining": "{{count}} cabang wawancara tersisa",
  "confirmation.price_preview":
    "Jika layanan Bali Zero yang didukung memiliki harga terverifikasi, harganya akan tampil sebagai satu jumlah all-inclusive.",
  "confirmation.cta": "Lihat opsi saya",

  "verdict.headline.SUPPORTED_CANDIDATES": "Jalur yang didukung ditemukan",
  "verdict.headline.HUMAN_REVIEW_REQUIRED":
    "Ini butuh manusia, bukan algoritma",
  "verdict.headline.NO_SUPPORTED_PATH":
    "Belum ada jalur yang didukung",
  "verdict.headline.TEMPORARILY_UNAVAILABLE":
    "Layanan keputusan terverifikasi belum dapat menyelesaikan penilaian ini",
  "verdict.headline.NEEDS_INPUT": "Informasi tambahan diperlukan",
  "verdict.evaluating": "Memeriksa aturan yang telah diverifikasi…",
  "verdict.eligibility.eligible": "Memenuhi syarat",
  "verdict.eligibility.likely": "Kemungkinan besar",
  "verdict.eligibility.conditional": "Bersyarat",
  "verdict.eligibility.likely-not": "Kemungkinan tidak",
  "verdict.state_description.SUPPORTED_CANDIDATES":
    "Mesin deterministik mendukung jalur yang ditampilkan berdasarkan fakta dan sumber bertanggal dalam penilaian ini.",
  "verdict.state_description.HUMAN_REVIEW_REQUIRED":
    "Tidak ada yang ditebak di sini. Konsultan Bali Zero meninjau kasus seperti ini secara langsung.",
  "verdict.state_description.NO_SUPPORTED_PATH":
    "Mesin ini belum menetapkan jalur yang didukung berdasarkan fakta ini. Ini bukan penetapan bahwa Anda tidak memenuhi syarat untuk semua jalur. Tinjau alasan dan jawaban Anda sebelum menentukan langkah berikutnya.",
  "verdict.state_description.TEMPORARILY_UNAVAILABLE":
    "Kami lebih memilih berterus terang daripada memalsukan hasil.",
  "verdict.state_description.NEEDS_INPUT":
    "Penilaian ini belum dapat menetapkan jalur yang didukung sampai detail yang belum tersedia dilengkapi.",
  "verdict.provenance_headline.CLIENT_GUARD":
    "Penilaian ini belum dapat diverifikasi",
  "verdict.provenance_headline.NETWORK_FAILURE":
    "Layanan keputusan tidak dapat dihubungi",
  "verdict.provenance_headline.SHADOW":
    "Verifikasi penilaian sedang berlangsung",
  "verdict.provenance_headline.PREVIEW":
    "Hanya pratinjau — bukan keputusan langsung",
  "verdict.provenance_description.CLIENT_GUARD":
    "Tidak ada rekomendasi yang ditampilkan. Tinjau jawaban Anda atau lanjutkan dengan konsultan.",
  "verdict.provenance_description.NETWORK_FAILURE":
    "Tidak ada hasil yang dibuat. Jawaban Anda tidak diganti dengan tebakan.",
  "verdict.provenance_description.SHADOW":
    "Penilaian Anda dikirim untuk verifikasi, tetapi tidak ada jalur visa yang ditampilkan selama enforcement publik dinonaktifkan.",
  "verdict.provenance_description.PREVIEW":
    "Layar ini memakai data uji untuk peninjauan produk dan tidak dapat mendukung rekomendasi.",

  "outcome.comparison_title": "Perbandingan jalur",
  "outcome.comparison_col.visa": "Jalur",
  "outcome.comparison_col.eligibility": "Kelayakan",
  "outcome.comparison_col.timeline": "Linimasa",
  "outcome.comparison_col.price": "Harga",
  "outcome.timeline_title": "Linimasa pemrosesan",
  "outcome.timeline_range": "Sekitar {{min}}–{{max}} hari",
  "outcome.price_label": "Harga all-inclusive",
  "outcome.price_all_inclusive":
    "Satu angka — tanpa pemisahan PNBP vs. biaya jasa, selalu.",
  "outcome.price_valid_until": "Penawaran berlaku hingga {{date}}",
  "outcome.price_free": "Gratis",
  "outcome.whatsapp_summary_header": "Ringkasan keputusan Visa Oracle:",
  "outcome.checklist_title": "Daftar periksa dokumen operasional",
  "outcome.next_steps_title": "3 langkah berikutnya",
  "outcome.next_steps.default.1":
    "Hubungi konsultan Bali Zero dengan ringkasan ini",
  "outcome.next_steps.default.2": "Siapkan dokumen yang tercantum di atas",
  "outcome.next_steps.default.3":
    "Pastikan linimasa Anda sebelum memesan perjalanan",
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
  "outcome.business_catalog_title": "Pilihan Bisnis lain untuk diperiksa",
  "outcome.d12_catalog_name": "Kunjungan prainvestasi — beberapa kali masuk",
  "outcome.d12_catalog_scope":
    "Untuk kunjungan prainvestasi atau menjajaki usaha baru, termasuk survei lapangan dan studi kelayakan.",
  "outcome.d12_catalog_status": "Kelayakan belum dipastikan",
  "outcome.d12_catalog_assessment":
    "Penilaian ini belum memastikan kelayakan Anda untuk D12. Periksa apakah rencana kegiatan dan dokumen Anda memenuhi persyaratannya.",
  "outcome.d12_catalog_source": "Persyaratan D12 — Imigrasi Indonesia",
  "q.business_activity.opt.preinvestment": "Survei atau studi kelayakan untuk memulai usaha",
  "outcome.order_note": "Ditampilkan sesuai urutan deterministik mesin. Ini bukan perbandingan kesesuaian atau rekomendasi visa terbaik.",
  "outcome.d12_duration_title": "Masa tinggal, perpanjangan, dan masa berlaku visa",
  "outcome.d12_duration": "D12 mengizinkan hingga 180 hari setiap kedatangan. Masa tinggal lebih lama memerlukan perpanjangan terpisah; penilaian ini tidak memberikannya. Masa berlaku visa adalah periode visa dapat digunakan, bukan izin tinggal terus-menerus selama periode tersebut. Perkiraan proses di bawah adalah ukuran operasional yang berbeda.",
  "outcome.conditions_title": "Syarat dan pemeriksaan yang masih perlu dipenuhi",
  "outcome.conditions_note": "Ini syarat berdasarkan sumber, bukan dokumen pemohon yang sudah diverifikasi. Wawancara ini belum memastikan bahwa Anda memenuhi setiap persyaratan permohonan.",
  "outcome.other_context": "Konteks aturan lainnya",
  "outcome.source_reference": "Sumber {{number}}",
  "outcome.rank": "Hasil {{rank}}",
  "outcome.axis.legal": "Kelayakan hukum",
  "outcome.axis.operational": "Ketersediaan operasional",
  "outcome.axis.service": "Layanan Bali Zero",
  "outcome.status.SUPPORTED": "Didukung",
  "outcome.status.CONDITIONAL": "Bersyarat",
  "outcome.status.NOT_SUPPORTED": "Tidak didukung",
  "outcome.status.UNKNOWN": "Belum diketahui",
  "outcome.status.AVAILABLE": "Tersedia",
  "outcome.status.TEMPORARILY_UNAVAILABLE": "Sementara tidak tersedia",
  "outcome.status.CONTACT_REQUIRED": "Perlu menghubungi kami",
  "outcome.status.NOT_OFFERED": "Tidak ditawarkan",
  "outcome.why_supported": "Fakta yang digunakan aturan pencocokan",
  "outcome.timeline_dates": "{{from}} sampai {{to}}",
  "outcome.timeline_basis": "Dihitung dari tanggal penilaian: {{date}}",
  "outcome.timeline_unavailable":
    "Linimasa tidak tersedia — belum ada estimasi kalender terverifikasi",
  "outcome.timeline_contact_required":
    "Linimasa memerlukan konfirmasi operasional",
  "outcome.documents_unknown": "Daftar periksa operasional belum tersedia",
  "outcome.documents_contact": "Syarat dari sumber di atas tetap relevan. Penilaian ini belum menyediakan daftar periksa terverifikasi untuk menyiapkan dan mengajukan permohonan khusus Anda.",
  "outcome.document_status.CONDITIONAL": "Bersyarat",
  "outcome.document_status.UNKNOWN": "Perlu dikonfirmasi",
  "outcome.needs_input_body":
    "Mesin tidak mengambil keputusan karena fakta berikut masih belum tersedia:",
  "outcome.needs_input_advisor_body":
    "Detail yang masih diperlukan tidak dapat dikumpulkan melalui pertanyaan tambahan dalam wawancara ini. Konsultan Bali Zero dapat meninjau informasi yang belum tersedia bersama Anda. Anda juga dapat mengubah jawaban yang tercatat di bawah; belum ada jalur yang didukung.",
  "outcome.answer_missing_input": "Jawab ini",
  "outcome.retryable": "Anda dapat mencoba evaluasi ini kembali dengan aman.",
  "outcome.not_retryable":
    "Seseorang perlu memeriksa ini sebelum Anda melanjutkan.",
  "outcome.sources_title": "Bukti yang dikembalikan bersama penilaian ini",
  "outcome.source_dates": "Awal keberlakuan tercatat {{effective}} · sumber diperiksa {{observed}}",
  "outcome.freshness.CURRENT": "Terkini pada waktu penilaian",
  "outcome.freshness.STALE": "Kedaluwarsa — perlu ditinjau",
  "outcome.freshness.UNKNOWN": "Kesegaran sumber belum diketahui",
  "outcome.assessment_dates":
    "Berlaku {{effective}} · diamati {{observed}} · dievaluasi {{evaluated}}",
  "outcome.provenance.CLIENT_GUARD.title": "Penahanan keamanan di perangkat",
  "outcome.provenance.CLIENT_GUARD.body":
    "Ini penahanan operasional. Penilaian belum dapat diverifikasi untuk ditampilkan; tidak ada jalur visa yang ditampilkan.",
  "outcome.provenance.NETWORK_FAILURE.title":
    "Layanan keputusan tidak tersedia",
  "outcome.provenance.NETWORK_FAILURE.body":
    "Mesin tidak memberikan jawaban. Tidak ada hasil cadangan atau kandidat yang dibuat-buat.",
  "outcome.provenance.SHADOW.title": "Mode verifikasi",
  "outcome.provenance.SHADOW.body":
    "Penilaian diukur dalam shadow mode. Tidak ada kandidat mesin yang ditampilkan, diurutkan, atau diganti dengan pratinjau.",
  "outcome.provenance.PREVIEW.title": "Data pratinjau",
  "outcome.provenance.PREVIEW.body":
    "Konten ini hanya untuk menguji antarmuka dan bukan rekomendasi.",
  "outcome.assumptions_receipt_title": "Asumsi & catatan, bertanggal",
  "outcome.assumptions_receipt_empty":
    "Penilaian ini tidak mencatat asumsi. Informasi yang belum tersedia atau belum pasti tetap dapat membatasi hasil.",
  "outcome.freshness_stamp": "Aturan keputusan dievaluasi {{date}}",
  "outcome.disclaimer.not_government":
    "Ini alat bantu keputusan privat, bukan layanan pemerintah.",
  "outcome.disclaimer.based_on_facts":
    "Hasil ini hanya mencerminkan data yang Anda masukkan dan sumber bertanggal yang ditampilkan di atas.",
  "outcome.disclaimer.not_approval":
    "Ini bukan persetujuan, jaminan, atau pengajuan resmi.",
  "outcome.disclaimer.complex_to_human":
    "Kasus kompleks atau ditandai selalu diteruskan ke manusia — Ditjen Imigrasi yang memutuskan, bukan alat ini.",
  "outcome.alternatives_title": "Tiga jalur alternatif yang layak dilihat",
  "outcome.alternatives_intro":
    "Ini bukan penurunan kelas — hanya yang paling sesuai.",
  "outcome.no_path_body":
    "Kombinasi yang Anda jelaskan tidak cocok dengan jalur yang didukung oleh aturan keputusan terverifikasi.",
  "outcome.no_path_reasons_title": "Alasan dari penilaian jalur",
  "outcome.no_path_reasons_context": "Mesin menilai beberapa produk visa. Alasan ini dapat berkaitan dengan produk yang berbeda, bukan gabungan persyaratan untuk satu visa. Jika suatu alasan tidak menyebut visa, respons ini tidak mengidentifikasi produknya.",
  "outcome.temporarily_unavailable_body":
    "Layanan keputusan belum dapat memverifikasi kasus ini. Tidak ada jalur cadangan yang dibuat-buat.",
  "outcome.human_review_body":
    "Kasus Anda butuh penilaian manusia — tidak ada yang ditebak atas nama Anda.",
  "outcome.overstay_reassurance":
    "Overstay bisa diselesaikan. Ini bukan akhir cerita Anda di sini.",

  "prototype.badge": "Dukungan keputusan visa",
  "prototype.badge.detail":
    "Hanya hasil mesin deterministik yang dapat tampil sebagai jalur yang didukung.",

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

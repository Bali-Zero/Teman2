// Editorial service guidance. Stable identities are pinned to the 2026-09-08 legacy inventory.
// Shared family guidance is composed with explicit route/term records, not guessed eligibility.
import type {
  DossierFamily,
  DossierRecord,
  DossierSource,
} from "./service-dossiers";

export const dossierSources = {
  visa: {
    label: "Immigration: current A1, B1, C1, C10 and E33G guidance",
    url: "https://bontang.imigrasi.go.id/public/layanan-publik/kategori/wna/sub/informasi-visa-republik-indonesia",
    checkedOn: "2026-09-08",
  },
  education: {
    label: "Immigration: formal education routes",
    url: "https://wonosobo.imigrasi.go.id/foreign-nationals-can-apply-for-indonesian-non-formal-education-visas-starting-july15-2025/",
    checkedOn: "2026-09-08",
  },
  slhs: {
    label: "Ministry of Health: SLHS register",
    url: "https://tpm.kemkes.go.id/rbi/web/",
    checkedOn: "2026-09-08",
  },
  excise: {
    label: "Customs: NPPBKC application guidance",
    url: "https://www.beacukai.go.id/pengajuan-nppbkc",
    checkedOn: "2026-09-08",
  },
  tax: {
    label: "DJP: annual returns in Coretax",
    url: "https://www.pajak.go.id/lapor-tahunan",
    checkedOn: "2026-09-08",
  },
  regional: {
    label: "Badung Bapenda: regional NPWPD registration",
    url: "https://bapenda.badungkab.go.id/pendaftaran-wajib-pajak-npwpd-air-tanah",
    checkedOn: "2026-09-08",
  },
  lkpm: {
    label: "OSS: quarterly and semester reporting notice (2025)",
    url: "https://oss.go.id/en/pengumuman/extended-deadline-for-submission-of-lkpm-for-q2-and-first-semester-of-2025",
    checkedOn: "2026-09-08",
  },
  building: {
    label: "Ministry of Public Works: PBG, SLF and existing IMB",
    url: "https://simbg.pu.go.id/",
    checkedOn: "2026-09-08",
  },
} satisfies Record<string, DossierSource>;

export const dossierFamilies = {
  a1: {
    purpose:
      "For an eligible short visitor who wants to use visa-free entry, with a departure already planned.",
    distinction:
      "A1 permits a single visit of up to 30 days without an extension. B1 is the option to examine when a longer visit may be needed.",
    scope: [
      "Nationality and entry-point review",
      "Travel-purpose and onward-journey check",
    ],
    preparation: [
      "Passport nationality and expiry",
      "Arrival port, travel dates and onward booking",
    ],
    limit:
      "Visa-free entry is not a work permission. Eligibility depends on nationality and the entry arrangements; assistance fees are confirmed separately.",
    next: "Check nationality and the planned departure before choosing visa-free arrival.",
    source: "visa",
  },
  voa: {
    purpose:
      "Arrival support for a short visit when the traveller is eligible for the Visa on Arrival route.",
    distinction:
      "B1 allows an initial stay of up to 30 days and one extension of up to 30 days. Buying the arrival service does not submit the later extension.",
    scope: [
      "Nationality and entry-point check",
      "Application document review and arrival guidance",
    ],
    preparation: [
      "Passport and recent photograph",
      "Arrival date, onward booking and visit purpose",
    ],
    limit:
      "Local employment and selling goods or services are outside this visitor route. The live price is not a statement that every third-party cost is included.",
    next: "Confirm arrival eligibility, then choose arrival support or the separate extension service.",
    source: "visa",
  },
  "voa-extension": {
    purpose:
      "For someone already in Indonesia on a B1 stay permit who needs the additional visit period.",
    distinction:
      "This is the one B1 extension, for up to 30 additional days. It does not issue a new arrival visa or restart a stay that has expired.",
    scope: [
      "Current B1 and entry-record review",
      "Extension preparation and appointment guidance",
    ],
    preparation: [
      "Current B1, arrival stamp or electronic entry record",
      "Passport, address and exact stay-expiry date",
    ],
    limit:
      "An expired permit needs a separate case review. A request or payment alone does not extend lawful stay.",
    next: "Have the existing permit reviewed before its expiry; do not wait for travel-day urgency.",
    source: "visa",
  },
  c1: {
    purpose:
      "A visit application for a traveller planning more time in Indonesia than a short arrival visit.",
    distinction:
      "C1 is single-entry, with an initial stay up to 60 days. Current official guidance also covers certain meetings and negotiations. Speaking at an event is a separate activity.",
    scope: [
      "Travel-purpose review",
      "Document preparation and application support",
    ],
    preparation: [
      "Passport, recent photograph and travel plan",
      "Evidence of living expenses and intended address",
    ],
    limit:
      "Permission for a visit does not create local employment rights. The issued stay end-date is separate from the deadline for using the visa to enter.",
    next: "Describe the actual activities, including any event role, before selecting the application.",
    source: "visa",
  },
  "c1-extension": {
    purpose:
      "An extension review for a current C1 visitor who wants to continue the same visit.",
    distinction:
      "This catalogue option requests an additional 60 days. Current C1 guidance permits extensions within a total stay ceiling of 180 days; the entry history and prior extensions determine the remaining room.",
    scope: [
      "Entry and extension-history review",
      "Extension application support",
    ],
    preparation: [
      "C1 permit and all previous extensions",
      "Passport, address and proposed departure date",
    ],
    limit:
      "This is not another entry visa. An additional full period cannot be assumed if the total permitted stay has already been used.",
    next: "Reconcile the current expiry with the entire stay history before requesting an extension.",
    source: "visa",
  },
  c2: {
    purpose:
      "Business-visit support for meetings, negotiations and a clearly described commercial itinerary.",
    distinction:
      "The catalogue retains the C2 Business name. C1 now includes some business activities, so the actual itinerary must be checked against current classifications rather than treating this older code as the only meeting route.",
    scope: [
      "Meeting itinerary and host review",
      "Current visa-category selection and document preparation",
    ],
    preparation: [
      "Invitations and agenda",
      "Host details, passport and travel dates",
    ],
    limit:
      "A catalogue code does not establish that a route is currently available. Employment, production work and the right to earn locally require separate assessment.",
    next: "List the activities and hosts so the current application index can be confirmed.",
    source: "visa",
  },
  social: {
    purpose:
      "For a visit built around a social, cultural or humanitarian programme with an identifiable organiser.",
    distinction:
      "A social programme differs from a holiday because the organiser, your role and the planned activities drive the application review.",
    scope: [
      "Programme and host review",
      "Application checklist and sponsor coordination",
    ],
    preparation: [
      "Host invitation and programme outline",
      "Role, funding arrangements and visit dates",
    ],
    limit:
      "Volunteer or unpaid status alone does not establish immigration permission. The current index and sponsor requirements need confirmation.",
    next: "Describe what you will do each day, including any teaching, fieldwork or payments.",
  },
  arts: {
    purpose:
      "For performers, artists or their event teams preparing a specific music or arts engagement.",
    distinction:
      "The C7A/B/C catalogue groups several roles. Performer, crew and organiser responsibilities must be separated before choosing a subcategory.",
    scope: [
      "Event-role classification",
      "Invitation and engagement-document review",
    ],
    preparation: [
      "Event dates and venue",
      "Contract, organiser invitation and a description of your role",
    ],
    limit:
      "This is not a general work visa. The grouped label does not establish a single permission or stay length for everyone on the event team.",
    next: "Identify each participant’s role and remuneration for a route-specific checklist.",
  },
  sports: {
    purpose:
      "For athletes, officials and support personnel travelling for a named sporting event.",
    distinction:
      "An athlete’s participation and an official’s or referee’s duties are different applications even when they concern the same competition.",
    scope: [
      "Role and event review",
      "Organiser and application-document coordination",
    ],
    preparation: [
      "Competition invitation and schedule",
      "Accreditation, team role and passport",
    ],
    limit:
      "The grouped C8A/B label is not a determination of the correct subcategory. Ordinary employment outside the event is excluded.",
    next: "Share the event invitation and exact role before selecting the category.",
  },
  speaker: {
    purpose:
      "For a speaker or presenter invited to contribute to a meeting, convention or exhibition.",
    distinction:
      "Speaking is different from attending as a participant. Official C10 guidance addresses speakers and presenters and permits event remuneration, but not an employment relationship.",
    scope: [
      "Speaker-role and invitation review",
      "Sponsor and application-document preparation",
    ],
    preparation: [
      "Invitation describing the agenda and presentation",
      "Engagement terms, passport and event dates",
    ],
    limit:
      "An event engagement is not unrestricted employment. Broader work or recurring duties need a separate route review.",
    next: "Confirm the presentation, organiser and payment terms before the application.",
    source: "visa",
  },
  trial: {
    purpose:
      "A pre-application review for a proposed work trial at an Indonesian organisation.",
    distinction:
      "A trial, an internship and starting a job are distinct activities. The label must not be used to turn an ordinary employment role into a visit.",
    scope: [
      "Host and trial-activity assessment",
      "Immigration and labour-requirement review",
    ],
    preparation: [
      "Trial agreement and host details",
      "Tasks, compensation, supervision and intended dates",
    ],
    limit:
      "The duration currently available needs confirmation. Do not begin duties until the permitted activity and current route are confirmed.",
    next: "Provide a written description of the proposed trial before making work or travel commitments.",
  },
  internship: {
    purpose:
      "For a structured placement with a host organisation and a defined learning programme.",
    distinction:
      "The placement’s academic or industrial purpose determines the appropriate subcategory. The two catalogue periods describe different requests, not interchangeable grants.",
    scope: [
      "Placement and host review",
      "Application and supporting-letter preparation",
    ],
    preparation: [
      "Placement agreement and training plan",
      "Host, supervision arrangements and any school affiliation",
    ],
    limit:
      "The requested duration and C22 subcategory need current confirmation. A placement does not automatically permit unrelated paid work.",
    next: "Match the placement dates and duties to a current route before booking travel.",
  },
  bridging: {
    purpose:
      "A review of continuity of stay while a change of immigration status is being arranged.",
    distinction:
      "Bridging concerns the interval between permissions. It is different from renewing the underlying visit or residence permit.",
    scope: [
      "Current-status and application-timeline review",
      "Assessment of the available transition procedure",
    ],
    preparation: [
      "Current permit and exact expiry",
      "Pending-application receipts and intended new status",
    ],
    limit:
      "No automatic protection arises from a pending application. Availability and any conditions must be confirmed for the actual status.",
    next: "Review the existing expiry and filing timeline before relying on a transition arrangement.",
  },
  d1: {
    purpose:
      "For a tourism plan involving repeated trips to Indonesia rather than one continuous visit.",
    distinction:
      "The requested validity is the window for repeated entries, not the length of each stay. A longer validity is useful for a longer travel programme, but does not extend each visit automatically.",
    scope: [
      "Travel-pattern and current-category review",
      "Multiple-entry application preparation",
    ],
    preparation: [
      "Passport and recurring travel plan",
      "Evidence of funds and intended activities",
    ],
    limit:
      "Each entry has its own stay limit. Current availability, entry conditions and stay length must be checked before applying.",
    next: "Choose the requested validity around actual trips, then verify each-visit limits.",
  },
  d2: {
    purpose:
      "For recurring business visits with a documented pattern of meetings or negotiations.",
    distinction:
      "Unlike one-off meeting support, this request concerns repeat entries over the chosen validity period. Visa validity must not be read as continuous residence.",
    scope: [
      "Recurring-business itinerary review",
      "Host and multiple-entry document preparation",
    ],
    preparation: [
      "Meeting plan and business counterparts",
      "Passport, proposed trips and business background",
    ],
    limit:
      "The D2 catalogue label requires current-index confirmation. A business-visit service does not establish local employment rights.",
    next: "Describe the frequency and substance of visits before selecting the requested validity.",
  },
  d12: {
    purpose:
      "For a prospective investor planning repeat exploratory visits before deciding on a business investment.",
    distinction:
      "Investigation is the planning stage. It is different from operating an existing business or seeking residence on the basis of an established investment.",
    scope: [
      "Exploration plan review",
      "Host, target-sector and application-document preparation",
    ],
    preparation: [
      "Investment outline and proposed visits",
      "Potential sites or counterparties and passport",
    ],
    limit:
      "This service does not create a company or establish investor-residence eligibility. Current category and period availability need confirmation.",
    next: "Separate research visits from any planned operational duties in your brief.",
  },
  working: {
    purpose:
      "Residence-application support connected to a defined role with an Indonesian employer.",
    distinction:
      "An employer-based case is assessed through the role and sponsoring organisation. It differs from foreign-employer remote work and from shareholder-based residence.",
    scope: [
      "Employer and role review",
      "Coordination of immigration documents and relevant labour approvals",
    ],
    preparation: [
      "Employment terms, job description and qualifications",
      "Employer documents and current immigration status",
    ],
    limit:
      "Labour approvals, government charges and employer obligations must be itemised in the quote. A residence application is not permission to start work.",
    next: "Have the employer confirm the role and proposed start date before preparing the case.",
  },
  investor: {
    purpose:
      "Residence support for a company shareholder whose investment and role need to be reviewed together.",
    distinction:
      "Share ownership, company compliance and actual duties matter. This differs from an employee-sponsored application; the two-year catalogue option is a requested term, not an eligibility finding.",
    scope: [
      "Shareholding and company-document review",
      "Residence application preparation",
    ],
    preparation: [
      "Deed and amendments, shareholder register and company licences",
      "Role description, passport and current permit",
    ],
    limit:
      "Owning a company does not by itself establish residence eligibility or unrestricted work rights. Investment thresholds need a current case check.",
    next: "Review the company record and actual role before relying on the investor route.",
  },
  freelance: {
    purpose:
      "A specialist review of an engagement sold in this catalogue under the Freelance E23 label.",
    distinction:
      "“Freelance” is a commercial description, not a general permission to take any Indonesian client. The engagement, sponsor and precise E23 subcategory must be established.",
    scope: [
      "Contract and role assessment",
      "Current work-category and sponsorship review",
    ],
    preparation: [
      "Contracts, client or employer locations and duties",
      "Qualifications, passport and current permit",
    ],
    limit:
      "The available duration and permitted work require a route-specific review. No activity should be treated as authorised by this catalogue label.",
    next: "Provide the actual engagement before choosing a route or accepting work.",
  },
  remote: {
    purpose:
      "For someone carrying out duties in Indonesia for a company established outside Indonesia.",
    distinction:
      "E33G is tied to foreign-company work. It differs from local employment and from an undefined freelance activity; official guidance gives a one-year stay.",
    scope: [
      "Foreign-employer evidence review",
      "Residence application and renewal preparation",
    ],
    preparation: [
      "Foreign employment contract and company information",
      "Income evidence, passport and current immigration status",
    ],
    limit:
      "The service does not establish eligibility for local employment. Financial and documentary requirements must be checked against the current application.",
    next: "Confirm the employer’s location and your contractual duties before preparing the file.",
    source: "visa",
  },
  secondhome: {
    purpose:
      "A longer-term residence review for someone considering Indonesia as a second home.",
    distinction:
      "The five-year catalogue request is distinct from the senior-specific options. Qualifying financial evidence and any post-arrival commitments must be reviewed before choosing it.",
    scope: [
      "Residence-plan and financial-evidence review",
      "Application preparation and post-arrival obligation checklist",
    ],
    preparation: [
      "Passport, intended residence and supporting financial records",
      "Any proposed qualifying asset documentation",
    ],
    limit:
      "Historic deposit, property-value and deadline claims have not been revalidated here. Application support does not include purchasing an asset or managing client funds.",
    next: "Verify the current qualification route and obligations before committing funds.",
  },
  "senior-e": {
    purpose:
      "A senior-residence review for the E33E route and its longer-term residence plan.",
    distinction:
      "The E33E and E33F catalogue entries must not be treated as identical funding routes. The current age, income, deposit and sponsor conditions need to be checked separately.",
    scope: [
      "Senior-route and financial-evidence review",
      "Application or existing-permit renewal preparation",
    ],
    preparation: [
      "Passport and proof of age",
      "Income and asset evidence, address and existing permit if renewing",
    ],
    limit:
      "Old monetary thresholds and the claim of automatic annual renewal are not carried forward. The issued permit determines the renewal starting point.",
    next: "Compare the current E33E conditions with the intended length of residence.",
  },
  "senior-f": {
    purpose:
      "A review of the senior-residence request listed under E33F, including the applicant’s existing status.",
    distinction:
      "This catalogue presents a one-year request separately from E33E’s longer-term option. It does not establish that an income-only or deposit-free route is currently available.",
    scope: [
      "Current-category and sponsor review",
      "Income-document and application preparation",
    ],
    preparation: [
      "Passport, age and residence plan",
      "Income records, sponsor details and current permit if present",
    ],
    limit:
      "Current age, income and deposit conditions require verification for this route. Confirm these before committing to the residence plan.",
    next: "Check whether this indexed route remains applicable to the case before selecting it.",
  },
  school: {
    purpose:
      "Residence support for a student entering primary or secondary education in Indonesia.",
    distinction:
      "E30A concerns school education; E30B concerns higher education. The requested period should fit the admission and study programme.",
    scope: [
      "School admission and sponsor review",
      "Student application-document coordination",
    ],
    preparation: [
      "Acceptance letter and study dates",
      "Student passport, guardian information and funding evidence",
    ],
    limit:
      "A student permit does not automatically give a parent residence or employment rights. Family applications require their own review.",
    next: "Start with the school’s acceptance and sponsorship arrangements.",
    source: "education",
  },
  university: {
    purpose:
      "Residence support for study at a higher-education institution in Indonesia.",
    distinction:
      "E30B is the higher-education route, distinct from E30A school education. Official guidance lists one-, two- and four-year study options; the programme determines the appropriate request.",
    scope: [
      "Admission and programme-duration review",
      "Institution and student-document coordination",
    ],
    preparation: [
      "University acceptance and programme details",
      "Passport, funding evidence and institution contact",
    ],
    limit:
      "The course length does not itself guarantee a matching permit. Employment and family residence are separate questions.",
    next: "Align the requested period with the university’s admission and sponsorship documents.",
    source: "education",
  },
  spouse: {
    purpose:
      "Family-residence support based on a documented marriage and the sponsoring spouse’s status.",
    distinction:
      "A spouse application relies on the marriage and sponsor relationship. Other dependants use a separate family route; the sponsor’s nationality and permit affect the application.",
    scope: [
      "Marriage and sponsor-status review",
      "Family residence application preparation",
    ],
    preparation: [
      "Marriage certificate and any translations or legalisation",
      "Both spouses’ identity and immigration documents",
    ],
    limit:
      "Marriage alone does not complete a residence application. Work rights and the available permit term require their own assessment.",
    next: "Confirm the sponsor’s status and the marriage-document chain first.",
  },
  dependent: {
    purpose:
      "Residence support for an eligible family member joining a principal resident.",
    distinction:
      "The principal resident’s status and the family relationship drive this case. A dependent permit is separate from the principal’s application and from a spouse-specific case.",
    scope: [
      "Relationship and principal-permit review",
      "Dependent application-document preparation",
    ],
    preparation: [
      "Birth or relationship documents",
      "Principal resident’s passport and permit, and dependant’s passport",
    ],
    limit:
      "Each family member requires a separate status review. A dependent application does not itself establish a right to work.",
    next: "Match the family relationship and requested stay to the principal’s valid permission.",
  },
  born: {
    purpose:
      "A residence-document review for a foreign child born in Indonesia.",
    distinction:
      "This concerns the child’s immigration status. Reporting the birth and obtaining civil documents are separate steps and may also be needed.",
    scope: [
      "Parents’ status and child-document review",
      "Coordination of the applicable immigration application",
    ],
    preparation: [
      "Birth record and parents’ passports and permits",
      "Child’s passport or information on its application",
    ],
    limit:
      "Birth in Indonesia does not by itself determine citizenship or residence permission. Local reporting deadlines must be verified promptly.",
    next: "Start with the birth date and parents’ current permits; identify missing civil and travel documents.",
  },
  retirement: {
    purpose:
      "Residence-planning support for someone moving to Indonesia after retirement.",
    distinction:
      "This catalogue route is reviewed separately from the E33E and E33F senior options. Age, income, sponsor and intended activities determine which current pathway fits.",
    scope: [
      "Retirement-plan and sponsor review",
      "Financial and residence-document preparation",
    ],
    preparation: [
      "Passport and proof of age",
      "Retirement or income evidence, accommodation plan and existing permit",
    ],
    limit:
      "Current age and financial conditions require individual verification. Retirement residence is not presented as permission for local employment.",
    next: "Compare the current retirement and senior routes before committing to a sponsor or accommodation.",
  },
  "kitap-investor": {
    purpose:
      "A permanent-residence review for an investor with an established immigration and company history.",
    distinction:
      "KITAP is a separate application from extending KITAS. Investment records and the qualifying residence history must be reviewed; the MERP component concerns re-entry.",
    scope: [
      "Residence-history and company review",
      "KITAP and re-entry document coordination",
    ],
    preparation: [
      "Current and previous stay permits",
      "Company records, shareholding evidence and travel plans",
    ],
    limit:
      "The scope covers KITAP and re-entry document coordination. The quote identifies the service work and government charges; qualification and the re-entry period require separate confirmation.",
    next: "Review the complete residence history and company position before proceeding.",
  },
  "kitap-dependent": {
    purpose:
      "A permanent-residence review for a family member linked to a principal resident.",
    distinction:
      "A family relationship and the principal’s permission matter alongside residence history. This is not simply a longer dependent KITAS renewal.",
    scope: [
      "Family and principal-status review",
      "KITAP and re-entry document coordination",
    ],
    preparation: [
      "Family certificates and principal’s permit",
      "Applicant’s complete residence history and passport",
    ],
    limit:
      "Eligibility and re-entry validity are separate checks. Family members are not automatically included in one application or one price.",
    next: "Establish the principal’s status and each applicant’s qualifying history.",
  },
  "kitap-retirement": {
    purpose:
      "A permanent-residence review following an established retirement-residence history.",
    distinction:
      "This application examines a longer residence history than an ordinary retirement extension. The MERP component must be considered separately for future travel.",
    scope: [
      "Retirement-status and residence-history review",
      "KITAP and re-entry application preparation",
    ],
    preparation: [
      "Previous permits and current passport",
      "Sponsor, income and accommodation records",
    ],
    limit:
      "The scope covers KITAP and re-entry application preparation. The quote identifies the service work and government charges; neither permanent residence nor a particular re-entry period is automatic.",
    next: "Reconcile the permit history, sponsor and travel plans before requesting the package.",
  },
  reset: {
    purpose:
      "Help diagnosing access or record problems in an existing Molina/eVisa account.",
    distinction:
      "Reset support starts from an existing account. Account creation is a separate service; neither should be assumed to change immigration status.",
    scope: [
      "Account problem assessment",
      "Recovery and record-correction route identification",
    ],
    preparation: [
      "Account email and a description of the error",
      "Relevant application reference, with sensitive data shared securely",
    ],
    limit:
      "No password or verification code should be sent through a public enquiry. The exact recovery action and ownership checks are confirmed first.",
    next: "Describe the error and whether you still control the account email.",
  },
  create: {
    purpose:
      "Assistance setting up the immigration account needed for a planned application.",
    distinction:
      "Creation is for a new account; use recovery support when an account already exists. “Express” is a catalogue label, not a visa-processing guarantee.",
    scope: [
      "Account setup guidance",
      "Applicant or sponsor profile and document-readiness review",
    ],
    preparation: [
      "Account-holder role and an email you control",
      "Purpose of the intended application",
    ],
    limit:
      "Creating an account does not issue a visa. Credentials and verification codes remain with the account holder.",
    next: "Confirm whether the applicant or sponsor needs the account before creating a duplicate.",
  },
  passport: {
    purpose:
      "Application-preparation support for an Indonesian passport in the selected catalogue format.",
    distinction:
      "An electronic passport has a chip; the format and requested validity are separate choices. This service concerns Indonesian passports, not renewal of a foreign passport.",
    scope: [
      "Applicant and requested-format review",
      "Document and appointment preparation",
    ],
    preparation: [
      "Existing passport, if any",
      "Indonesian identity and civil records, and travel timing",
    ],
    limit:
      "The five- and ten-year labels do not establish current availability or entitlement for every age group. Issuance and validity are determined by immigration.",
    next: "Confirm age, applicant circumstances and local office availability before selecting the format.",
  },
  sktt: {
    purpose:
      "Civil-registration support for a temporary resident’s Surat Keterangan Tempat Tinggal.",
    distinction:
      "SKTT records temporary residence with civil registration. It is distinct from the immigration stay permit and from a local domicile letter.",
    scope: [
      "Local civil-registration checklist",
      "Application and address-document coordination",
    ],
    preparation: [
      "Passport and current stay permit",
      "Local address evidence and sponsor information",
    ],
    limit:
      "This registration does not extend immigration permission. The local office’s current checklist and deadline need confirmation.",
    next: "Identify the civil-registration office for the actual residential address.",
  },
  skck: {
    purpose:
      "Document support for a police record certificate requested for a specific administrative purpose.",
    distinction:
      "SKCK is a police certificate, not an immigration permit. The requesting institution’s purpose and format matter before an application is prepared.",
    scope: [
      "Purpose and issuing-office review",
      "Supporting-document and application coordination",
    ],
    preparation: [
      "Requesting institution’s instructions",
      "Identity, residence history and current status documents",
    ],
    limit:
      "The certificate’s content is determined by the police. Translation, legalisation and overseas acceptance are separate scope items.",
    next: "Confirm who will receive the certificate and what they require.",
  },
  domicile: {
    purpose:
      "Support documenting a residential address for an administrative application.",
    distinction:
      "A domicile letter confirms an address for a receiving authority. It is different from SKTT registration and does not create residence rights.",
    scope: [
      "Receiving-authority and address-evidence review",
      "Local letter and supporting-document coordination",
    ],
    preparation: [
      "Address and occupancy evidence",
      "Identity documents and the receiving office’s checklist",
    ],
    limit:
      "The correct issuing office and document form vary with purpose and locality. A letter is not proof of property ownership.",
    next: "Identify the receiving authority before requesting the address document.",
  },
  "mutation-passport": {
    purpose:
      "Update support when a new passport needs to be reflected in an existing immigration record.",
    distinction:
      "This updates the document linked to an existing permit. It neither renews the passport nor grants a new stay period.",
    scope: [
      "Old/new passport and permit reconciliation",
      "Immigration-record update preparation",
    ],
    preparation: [
      "Old and new passports",
      "Current permit and any relevant travel records",
    ],
    limit:
      "Travel on mismatched records may need separate guidance. A passport update does not extend the existing stay.",
    next: "Have both passports and the current permit checked before the next trip.",
  },
  "mutation-address": {
    purpose:
      "Support updating the residential address attached to an immigration record within the same office jurisdiction.",
    distinction:
      "A move within one immigration office’s jurisdiction differs from a transfer between two offices. The new address decides which process is needed.",
    scope: [
      "Address and office-jurisdiction review",
      "Residence-record update preparation",
    ],
    preparation: [
      "Old and new addresses with occupancy evidence",
      "Passport, permit and sponsor details",
    ],
    limit:
      "An immigration update does not automatically update civil registration or company records.",
    next: "Confirm the new address and relevant office before selecting this service.",
  },
  "mutation-transfer": {
    purpose:
      "Support coordinating an address move between two immigration-office jurisdictions.",
    distinction:
      "The “2 Kanim” service concerns a transfer between offices; a move inside the same jurisdiction uses the simpler address-update request.",
    scope: [
      "Origin/destination jurisdiction review",
      "Transfer and new-address document coordination",
    ],
    preparation: [
      "Current permit and passport",
      "Old/new address evidence and sponsor details",
    ],
    limit:
      "Both office requirements must be established. Civil-registration changes and sponsor changes may be separate work.",
    next: "Identify both addresses and the move date so the transfer sequence can be reviewed.",
  },
  "birth-under": {
    purpose:
      "Prompt birth-reporting support for a foreign child while the reporting timeline is being established.",
    distinction:
      "The “Under” label refers to an ordinary reporting case. It differs from a delayed report; the actual deadline depends on the applicable process and office.",
    scope: [
      "Birth date and parents’ status review",
      "Reporting checklist and document coordination",
    ],
    preparation: [
      "Birth record and parents’ permits",
      "Parents’ passports and child’s travel-document status",
    ],
    limit:
      "The applicable reporting deadline requires verification with the responsible office. This listing does not determine whether the report is within time.",
    next: "Provide the birth date and location promptly so the correct deadline can be established.",
  },
  "birth-up": {
    purpose:
      "A review of a birth report that may be late or needs additional explanation.",
    distinction:
      "The “Up” label flags possible delayed reporting. It is not a published grace period or a way to bypass missing immigration documents.",
    scope: [
      "Timeline and missing-record assessment",
      "Delayed-reporting procedure and document coordination",
    ],
    preparation: [
      "Birth record, location and full reporting history",
      "Parents’ passports/permits and previous office correspondence",
    ],
    limit:
      "Office-specific deadlines and any penalty treatment need verification. The actual case must be assessed before quoting remedial work.",
    next: "Set out the dates and any previous reporting attempts for a delay review.",
  },
  "cancel-rptka": {
    purpose:
      "Employer-side support when a foreign-worker utilisation approval needs to be closed or updated after an engagement ends.",
    distinction:
      "RPTKA concerns the employment approval record. It is separate from cancelling the worker’s immigration stay permit through EPO or an offshore procedure.",
    scope: [
      "Employer approval and employment-end review",
      "Cancellation or update document coordination",
    ],
    preparation: [
      "Existing RPTKA record and employer documents",
      "Termination or end-of-assignment evidence and worker status",
    ],
    limit:
      "Closing a labour record does not itself close immigration status. The required sequence must cover both systems.",
    next: "Reconcile the end date with labour and immigration records together.",
  },
  "cancel-report": {
    purpose:
      "Employer reporting support where the registered workforce or business reporting record needs closure or amendment.",
    distinction:
      "Wajib Lapor reporting is different from the worker-specific utilisation approval and from a stay-permit cancellation.",
    scope: [
      "Reporting-account and closure-reason review",
      "Employer reporting update preparation",
    ],
    preparation: [
      "Company reporting reference and employer documents",
      "Reason for closure/change and employment records",
    ],
    limit:
      "This service does not automatically cancel RPTKA or an immigration permit. The precise report being changed must be identified.",
    next: "Identify the reporting record and reason for amendment before requesting cancellation.",
  },
  labour: {
    purpose:
      "Support limited to the foreign-worker employment approval file for the requested assignment period.",
    distinction:
      "This is the labour-document component, separate from a KITAS package. The IMTA catalogue wording requires mapping to the currently applicable approval process.",
    scope: [
      "Employer, role and assignment-period review",
      "Labour approval documentation and filing coordination",
    ],
    preparation: [
      "Job description, contract and qualifications",
      "Employer records and planned assignment dates",
    ],
    limit:
      "A labour approval alone is not a visa or residence permit. The requested period is subject to the role and current approval rules.",
    next: "Confirm who handles the immigration component so neither part is left out.",
  },
  epo: {
    purpose:
      "Onshore closure support for a stay permit when the holder is preparing to leave Indonesia.",
    distinction:
      "EPO concerns ending a stay while the holder is still in Indonesia. The offshore closure service addresses a holder who has already left.",
    scope: [
      "Departure and permit-status review",
      "Sponsor and cancellation-document coordination",
    ],
    preparation: [
      "Current permit, passport and planned departure",
      "Sponsor’s closure documents and employment-end details if relevant",
    ],
    limit:
      "The permitted departure window and linked labour-record steps must be confirmed. Cancelling a permit does not issue a replacement visa.",
    next: "Coordinate the intended departure date with the permit-closure sequence.",
  },
  erp: {
    purpose:
      "Offshore review and closure support for a stay permit after its holder has left Indonesia.",
    distinction:
      "This catalogue’s ERP entry is a closure service, not a promise of re-entry. Use the onshore EPO service when the holder is still in Indonesia.",
    scope: [
      "Exit record and current-permit review",
      "Sponsor and offshore-closure document coordination",
    ],
    preparation: [
      "Passport, permit and proof of departure",
      "Sponsor information and plans for any future return",
    ],
    limit:
      "Permit-closure support does not authorise another entry. Any future visa requires its own review.",
    next: "Confirm the holder is abroad and establish how the existing permit will be closed.",
  },
  driving: {
    purpose:
      "Application-preparation support for an Indonesian driving licence appropriate to the intended vehicle.",
    distinction:
      "SIM licensing is separate from immigration permission. Motorcycle and car use require the relevant licence category.",
    scope: [
      "Licence-category and applicant-document review",
      "Application and appointment guidance",
    ],
    preparation: [
      "Passport and immigration status",
      "Existing driving licence and intended vehicle category",
    ],
    limit:
      "Testing, medical requirements and issuance remain with the responsible authority. Assistance cannot substitute for a required examination.",
    next: "Identify the vehicle and applicant status before preparing the licence request.",
  },
  urgent: {
    purpose:
      "A feasibility enquiry for an unusually short processing target attached to an identified application.",
    distinction:
      "The one-, two- and three-day catalogue entries describe requested targets. They are not separate visa permissions and must be tied to the underlying service.",
    scope: [
      "Deadline and document-readiness check",
      "Assessment of current processing availability",
    ],
    preparation: [
      "Exact underlying service and deadline",
      "Application status, complete documents and reason for urgency",
    ],
    limit:
      "No turnaround is promised by the catalogue label. Authority processing, appointments and incomplete documents may make the target unavailable.",
    next: "Confirm availability and a written scope before relying on the requested target.",
  },
  revision: {
    purpose:
      "For an existing company whose legal records need to reflect a change in ownership, management, address, activity or capital.",
    distinction:
      "A revision updates an existing entity. It differs from incorporating a new company and may require changes across the deed, AHU, OSS and tax records.",
    scope: [
      "Director/shareholder and business-activity amendments",
      "Address and capital changes",
      "Notarial and Ministry of Law filing coordination",
    ],
    preparation: [
      "Current deed, amendments and approval records",
      "NIB, company tax record and a precise proposed-change list",
    ],
    limit:
      "Third-party notary charges and follow-on licence changes are itemised separately. An amendment does not by itself authorise a new regulated activity.",
    next: "Set out the current record and proposed change so the affected registrations can be mapped.",
  },
  slhs: {
    purpose:
      "For a food business preparing the hygiene and sanitation documentation relevant to its operation.",
    distinction:
      "SLHS means Sertifikat Laik Higiene Sanitasi. It concerns hygiene certification; company incorporation and permission to sell alcohol are separate services.",
    scope: [
      "Business-category and local health-office checklist",
      "Hygiene-document preparation",
      "Inspection and Dinas Kesehatan coordination where applicable",
    ],
    preparation: [
      "NIB, location and food-service activity",
      "Premises, hygiene practices and staff-training records available",
    ],
    limit:
      "Applicability, inspection requirements and timing depend on the business category and local review. A café label alone does not establish the required certification.",
    next: "Confirm the food-service category and premises before assembling the local checklist.",
    source: "slhs",
  },
  alcohol: {
    purpose:
      "For an operator whose sale or distribution of alcoholic beverages needs an excise-licensing review.",
    distinction:
      "The official acronym is NPPBKC; NPBBKC is retained only in this catalogue’s service name. Excise licensing is distinct from general business and food-hygiene approvals.",
    scope: [
      "Business activity, premises and beverage-range review",
      "Bea Cukai registration-document coordination",
      "Renewal requirements and record handover",
    ],
    preparation: [
      "Company and premises documents",
      "Sales model, beverage specifications and existing licences",
    ],
    limit:
      "This is not a universal permission to sell every beverage at every site. Product-class conditions and timing require case-specific confirmation.",
    next: "Identify the premises, sales model and beverage range for the excise-office checklist.",
    source: "excise",
  },
  formation: {
    purpose:
      "For founders establishing an Indonesian company and defining how it will actually operate.",
    distinction:
      "PT PMA and PT PMDN describe different investment structures. Shareholders, activities and location must be reviewed before choosing one; an existing entity may instead need a revision.",
    scope: [
      "Company registration and deed coordination",
      "NIB/OSS application and activity-specific licence review",
      "National tax-registration and bank-account assistance",
    ],
    preparation: [
      "Proposed shareholders and directors",
      "Activities, operating address and capital plan",
    ],
    limit:
      "Notarial work, bank approval and sector licences are confirmed in the scope. Incorporation does not automatically complete every operational permission; a company stamp is not a licence.",
    next: "Describe the business and ownership plan before selecting the formation route.",
  },
  npwp: {
    purpose:
      "For an individual who needs a national tax-registration or Coretax account-readiness review.",
    distinction:
      "Obtaining or validating a tax identity is different from filing an annual return. Existing registration must be checked before creating a duplicate record.",
    scope: [
      "Personal tax-registration review",
      "Coretax account and identity matching",
      "Document support and digital tax-identity retrieval where available",
    ],
    preparation: [
      "Identity and existing NPWP/NIK information",
      "Tax-residence context, contact details and current account-access status",
    ],
    limit:
      "Registration does not calculate tax due or file previous returns. Account credentials and verification codes remain private.",
    next: "Establish whether registration, identity correction or account activation is actually missing.",
    source: "tax",
  },
  npwpd: {
    purpose:
      "For a business reviewing registration for taxes administered by the relevant local government.",
    distinction:
      "NPWPD is a regional tax registration. It is not a replacement for the national corporate NPWP or a Coretax account.",
    scope: [
      "Local tax-object and registration review",
      "Company-document preparation",
      "Liaison with the responsible regional tax office",
    ],
    preparation: [
      "Company NIB and national tax record",
      "Business location, activity and relevant local tax object",
    ],
    limit:
      "The applicable regional tax and office depend on the location and activity. National tax registration is a separate scope item.",
    next: "Identify the locality and activity that create the regional registration question.",
    source: "regional",
  },
  "personal-return": {
    purpose:
      "Annual return preparation for an individual with income and supporting records to reconcile.",
    distinction:
      "This covers the person’s return. A company return is a separate filing, even where the individual is a director or shareholder.",
    scope: [
      "Income and withholding reconciliation",
      "Review of supported deductions and tax credits",
      "Annual return preparation and electronic filing",
    ],
    preparation: [
      "Income statements, withholding slips and previous return",
      "Asset/liability records and relevant overseas-income context",
    ],
    limit:
      "Tax-residence and foreign-income treatment need review; no tax saving is promised. Missing years or corrections are quoted separately.",
    next: "Gather the complete tax-year records and identify any changes in residence or income sources.",
    source: "tax",
  },
  "zero-return": {
    purpose:
      "Annual company-return support for an entity believed to have no operating activity in the relevant tax year.",
    distinction:
      "No sales does not necessarily mean no reportable transactions: bank charges, capital movements or expenses still need review. An operational return is used when the facts call for it.",
    scope: [
      "No-activity assessment and record reconciliation",
      "Company compliance documentation",
      "Annual company return preparation and electronic filing",
    ],
    preparation: [
      "Bank statements, ledgers and prior return",
      "Company tax status and evidence of any capital or expense movements",
    ],
    limit:
      "A director’s personal return is not automatically included. This service does not certify zero liability solely from an absence of revenue.",
    next: "Review all movements before classifying the year as a zero-activity filing.",
    source: "tax",
  },
  "operating-return": {
    purpose:
      "Annual corporate-return preparation for a company with business activity and financial records.",
    distinction:
      "An operational return reconciles the accounts and fiscal treatment. It differs from a zero-activity review and does not replace recurring monthly obligations.",
    scope: [
      "Financial-statement and ledger review",
      "Corporate annual return preparation",
      "Electronic filing and filing-receipt handover",
    ],
    preparation: [
      "Financial statements, ledger and bank reconciliations",
      "Withholding evidence, prior return and relevant monthly filings",
    ],
    limit:
      "Director personal filings, bookkeeping reconstruction and amended years require explicit scope. An annual return is not a statutory audit.",
    next: "Assess whether the books are complete before setting the filing timetable.",
    source: "tax",
  },
  "monthly-tax": {
    purpose:
      "Recurring reporting support organised around a company’s actual payroll, payments and taxable transactions.",
    distinction:
      "Monthly reporting concerns specific tax periods and obligations. It does not replace the annual return, BPJS administration or LKPM investment reporting.",
    scope: [
      "Applicable PPh 21/23/26 withholding review",
      "PPN reporting where the business is required to report VAT",
      "Payment-reference preparation and filing-calendar management",
    ],
    preparation: [
      "Payroll, invoices and payment ledger for the period",
      "Tax registration/PKP status and previous filing receipts",
    ],
    limit:
      "Not every business owes every listed tax. Payments, late periods and corrections are identified separately; the client authorises tax payments.",
    next: "Reconcile the month’s transactions and registration status before confirming the filing set.",
  },
  "bpjs-health": {
    purpose:
      "Company administration support for BPJS Kesehatan health-insurance registration and employee enrolment.",
    distinction:
      "Health-insurance administration is separate from BPJS Ketenagakerjaan employment protection and from payroll tax reporting.",
    scope: [
      "Employer-registration and employee-enrolment support",
      "Employee-data reconciliation",
      "Monthly changes and administration",
    ],
    preparation: [
      "Employer registration records",
      "Employee roster, family data and payroll information through a secure channel",
    ],
    limit:
      "The former two-employee minimum is not treated as a rule. Coverage eligibility, contributions and benefits require current scheme confirmation.",
    next: "Reconcile the employee roster with existing health-insurance registrations.",
  },
  "bpjs-employment": {
    purpose:
      "Company administration support for BPJS Ketenagakerjaan employment-protection registration.",
    distinction:
      "This concerns employment protection, separate from BPJS Kesehatan health insurance. Programme enrolment needs to match the employer and worker category.",
    scope: [
      "Employer and employee registration support",
      "Review of applicable programmes, including JHT, JP, JKK and JKM",
      "Monthly payroll and employee-change administration",
    ],
    preparation: [
      "Employer records and current scheme registrations",
      "Employee categories, joining/leaving dates and payroll data",
    ],
    limit:
      "The named programmes are not a complete entitlement determination. The former two-employee minimum is retired; benefits and contribution rates are not quoted here.",
    next: "Review worker categories and existing registrations before setting monthly administration.",
  },
  lkpm: {
    purpose:
      "Investment-activity reporting support for a business reporting project progress through OSS.",
    distinction:
      "LKPM describes investment realisation and operating progress. It is not an income-tax return and cannot be replaced by an SPT filing.",
    scope: [
      "Applicable reporting-period and OSS project review",
      "Investment, workforce and production-data reconciliation",
      "Submission and follow-up with the relevant authority",
    ],
    preparation: [
      "NIB and OSS project records",
      "Capital expenditure, workforce and project-progress records",
    ],
    limit:
      "Reporting frequency must be checked for the business and current rules. “Quarterly for everyone” is not a safe assumption; receipt and acceptance are separate stages.",
    next: "Confirm the project and reporting period before preparing investment-realisation figures.",
    source: "lkpm",
  },
  diligence: {
    purpose:
      "For a buyer or lessee who needs the property’s legal and documentary position examined before committing.",
    distinction:
      "Due diligence investigates the asset and identifies unresolved issues. It is distinct from drafting the transaction agreement or setting up a holding company.",
    scope: [
      "Certificate authenticity and ownership-history checks",
      "Zoning/land-use review and encumbrance searches",
      "Written findings, limitations and follow-up questions",
    ],
    preparation: [
      "Land certificate, site details and seller/lessor authority",
      "Existing agreements, building documents and intended use",
    ],
    limit:
      "A legal review is not a structural survey or a guarantee of title. Access to official records and technical experts is scoped explicitly.",
    next: "Collect the title and seller authority before a deposit or binding commitment.",
  },
  lease: {
    purpose:
      "For a proposed land or property lease whose commercial terms need to become a clear agreement.",
    distinction:
      "Hak Sewa is a right to lease, not ownership of the land. Contract drafting should follow a review of the lessor’s authority and the property’s intended use.",
    scope: [
      "English/Indonesian contract drafting",
      "Negotiation of term, renewal, assignment and exit clauses",
      "Notarial or legalisation coordination where appropriate",
    ],
    preparation: [
      "Proposed commercial terms and property documents",
      "Lessor authority, intended use and existing draft agreement",
    ],
    limit:
      "A lease does not establish automatic extension rights or a universal land-office registration process. Renewals, enforcement and registration treatment need specific review.",
    next: "Agree the intended term and renewal mechanism, then test them against the title and contract.",
  },
  building: {
    purpose:
      "For an owner or operator establishing which building approvals are needed for construction, alteration or use.",
    distinction:
      "PBG is the current building-approval process; SLF concerns fitness for use. An old IMB is not automatically invalid, and its treatment depends on the existing building and changes.",
    scope: [
      "PBG application and site/technical-plan coordination",
      "Review of applicable environmental documents, including AMDAL or UKL-UPL where required",
      "SLF and renovation-approval coordination",
    ],
    preparation: [
      "Land and existing building documents",
      "Architectural/technical plans, intended use and proposed alterations",
    ],
    limit:
      "Technical design, inspections and environmental approvals are separately scoped. An old IMB should not simply be relabelled PBG without checking the actual case.",
    next: "Compare the existing approvals with the building’s actual condition and intended use.",
    source: "building",
  },
  ownership: {
    purpose:
      "For an investor evaluating whether a PT PMA structure fits a proposed property activity.",
    distinction:
      "Company formation and land rights are separate questions. Review the business activity and the exact title, including any proposed HGB right, before choosing the holding structure.",
    scope: [
      "Company-purpose and property-right review",
      "Governance, liability and tax-implication assessment",
      "Transfer and succession-planning discussion",
    ],
    preparation: [
      "Proposed ownership chart and company activities",
      "Property title, intended use and investment/exit plan",
    ],
    limit:
      "A PT PMA does not confer unrestricted land ownership. “Asset protection” and “tax efficiency” are objectives to assess, not guaranteed outcomes.",
    next: "Review the title and activity alongside the structure before incorporating or transferring assets.",
  },
} satisfies Record<string, DossierFamily>;

export const dossierRecords = [
  {
    id: "svc-visa-001",
    name: "A1 Visa-Free Tourism",
    domain: "immigration",
    family: "a1",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-002",
    name: "B1 Visa on Arrival (VOA)",
    domain: "immigration",
    family: "voa",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-003",
    name: "B1 Visa on Arrival — Extension (+30 days)",
    domain: "immigration",
    family: "voa-extension",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-004",
    name: "C1 Tourism",
    domain: "immigration",
    family: "c1",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-005",
    name: "C1 Tourism — Extension (+60 days)",
    domain: "immigration",
    family: "c1-extension",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-006",
    name: "C2 Business",
    domain: "immigration",
    family: "c2",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-007",
    name: "C6 Social Activity",
    domain: "immigration",
    family: "social",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-008",
    name: "C7A,B,C — Music/Art",
    domain: "immigration",
    family: "arts",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-009",
    name: "C8A,B Sports Events",
    domain: "immigration",
    family: "sports",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-010",
    name: "C10 Speaker Visa",
    domain: "immigration",
    family: "speaker",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-011",
    name: "C18 Work Trial",
    domain: "immigration",
    family: "trial",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-012",
    name: "C22A&B Internship (60 Days)",
    domain: "immigration",
    family: "internship",
    route: "",
    variant: "60 Days",
  },
  {
    id: "svc-visa-013",
    name: "C22A&B Internship (180 Days)",
    domain: "immigration",
    family: "internship",
    route: "",
    variant: "180 Days",
  },
  {
    id: "svc-visa-014",
    name: "Bridging Visa",
    domain: "immigration",
    family: "bridging",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-015",
    name: "D1 Tourism (1 Year)",
    domain: "immigration",
    family: "d1",
    route: "",
    variant: "1 Year",
  },
  {
    id: "svc-visa-016",
    name: "D1 Tourism (2 Years)",
    domain: "immigration",
    family: "d1",
    route: "",
    variant: "2 Years",
  },
  {
    id: "svc-visa-017",
    name: "D1 Tourism (5 Years)",
    domain: "immigration",
    family: "d1",
    route: "",
    variant: "5 Years",
  },
  {
    id: "svc-visa-018",
    name: "D2 Business (1 Year)",
    domain: "immigration",
    family: "d2",
    route: "",
    variant: "1 Year",
  },
  {
    id: "svc-visa-019",
    name: "D2 Business (2 Years)",
    domain: "immigration",
    family: "d2",
    route: "",
    variant: "2 Years",
  },
  {
    id: "svc-visa-020",
    name: "D12 Business Investigation (1 Year)",
    domain: "immigration",
    family: "d12",
    route: "",
    variant: "1 Year",
  },
  {
    id: "svc-visa-021",
    name: "D12 Business Investigation (2 Years)",
    domain: "immigration",
    family: "d12",
    route: "",
    variant: "2 Years",
  },
  {
    id: "svc-visa-022",
    name: "Working KITAS (Altus/Onshore)",
    domain: "immigration",
    family: "working",
    route: "onshore",
    variant: "",
  },
  {
    id: "svc-visa-023",
    name: "Working KITAS (Offshore)",
    domain: "immigration",
    family: "working",
    route: "offshore",
    variant: "",
  },
  {
    id: "svc-visa-024",
    name: "Working KITAS (Extend)",
    domain: "immigration",
    family: "working",
    route: "renewal",
    variant: "",
  },
  {
    id: "svc-visa-025",
    name: "Investor KITAS 2 Years (Altus/Onshore)",
    domain: "immigration",
    family: "investor",
    route: "onshore",
    variant: "2 Years",
  },
  {
    id: "svc-visa-026",
    name: "Investor KITAS 2 Years (Offshore)",
    domain: "immigration",
    family: "investor",
    route: "offshore",
    variant: "2 Years",
  },
  {
    id: "svc-visa-027",
    name: "Investor KITAS 2 Years (Extend)",
    domain: "immigration",
    family: "investor",
    route: "renewal",
    variant: "2 Years",
  },
  {
    id: "svc-visa-028",
    name: "Freelance E23 (Altus/Onshore)",
    domain: "immigration",
    family: "freelance",
    route: "onshore",
    variant: "",
  },
  {
    id: "svc-visa-029",
    name: "Freelance E23 (Offshore)",
    domain: "immigration",
    family: "freelance",
    route: "offshore",
    variant: "",
  },
  {
    id: "svc-visa-030",
    name: "E33G Remote Worker (Altus/Onshore)",
    domain: "immigration",
    family: "remote",
    route: "onshore",
    variant: "",
  },
  {
    id: "svc-visa-031",
    name: "E33G Remote Worker (Offshore)",
    domain: "immigration",
    family: "remote",
    route: "offshore",
    variant: "",
  },
  {
    id: "svc-visa-032",
    name: "E33G Remote Worker (Extend)",
    domain: "immigration",
    family: "remote",
    route: "renewal",
    variant: "",
  },
  {
    id: "svc-visa-033",
    name: "E33 Second Home (5 Years)",
    domain: "immigration",
    family: "secondhome",
    route: "",
    variant: "5 Years",
  },
  {
    id: "svc-visa-034",
    name: "E33E Second Home Senior (5 Years)",
    domain: "immigration",
    family: "senior-e",
    route: "",
    variant: "5 Years",
  },
  {
    id: "svc-visa-035",
    name: "E33E Second Home Senior (Extend)",
    domain: "immigration",
    family: "senior-e",
    route: "renewal",
    variant: "",
  },
  {
    id: "svc-visa-036",
    name: "E33F Second Home Senior (1 Year, Offshore)",
    domain: "immigration",
    family: "senior-f",
    route: "offshore",
    variant: "1 Year",
  },
  {
    id: "svc-visa-037",
    name: "E33F Second Home Senior (1 Year, Altus/Onshore)",
    domain: "immigration",
    family: "senior-f",
    route: "onshore",
    variant: "1 Year",
  },
  {
    id: "svc-visa-038",
    name: "E33F Second Home Senior (Extend)",
    domain: "immigration",
    family: "senior-f",
    route: "renewal",
    variant: "",
  },
  {
    id: "svc-visa-039",
    name: "E30A Education Visa (1 Year)",
    domain: "immigration",
    family: "school",
    route: "",
    variant: "1 Year",
  },
  {
    id: "svc-visa-040",
    name: "E30A Education Visa (2 Years)",
    domain: "immigration",
    family: "school",
    route: "",
    variant: "2 Years",
  },
  {
    id: "svc-visa-041",
    name: "E30B Higher Education (1 Year)",
    domain: "immigration",
    family: "university",
    route: "",
    variant: "1 Year",
  },
  {
    id: "svc-visa-042",
    name: "E30B Higher Education (2 Years)",
    domain: "immigration",
    family: "university",
    route: "",
    variant: "2 Years",
  },
  {
    id: "svc-visa-043",
    name: "E30B Higher Education (4 Years)",
    domain: "immigration",
    family: "university",
    route: "",
    variant: "4 Years",
  },
  {
    id: "svc-visa-044",
    name: "Spouse 1 Year (Altus/Onshore)",
    domain: "immigration",
    family: "spouse",
    route: "onshore",
    variant: "1 Year",
  },
  {
    id: "svc-visa-045",
    name: "Spouse 1 Year (Offshore)",
    domain: "immigration",
    family: "spouse",
    route: "offshore",
    variant: "1 Year",
  },
  {
    id: "svc-visa-046",
    name: "Spouse 1 Year (Extend)",
    domain: "immigration",
    family: "spouse",
    route: "renewal",
    variant: "1 Year",
  },
  {
    id: "svc-visa-047",
    name: "Spouse 2 Years (Altus/Onshore)",
    domain: "immigration",
    family: "spouse",
    route: "onshore",
    variant: "2 Years",
  },
  {
    id: "svc-visa-048",
    name: "Spouse 2 Years (Offshore)",
    domain: "immigration",
    family: "spouse",
    route: "offshore",
    variant: "2 Years",
  },
  {
    id: "svc-visa-049",
    name: "Spouse 2 Years (Extend)",
    domain: "immigration",
    family: "spouse",
    route: "renewal",
    variant: "2 Years",
  },
  {
    id: "svc-visa-050",
    name: "Dependent 1 Year (Altus/Onshore)",
    domain: "immigration",
    family: "dependent",
    route: "onshore",
    variant: "1 Year",
  },
  {
    id: "svc-visa-051",
    name: "Dependent 1 Year (Offshore)",
    domain: "immigration",
    family: "dependent",
    route: "offshore",
    variant: "1 Year",
  },
  {
    id: "svc-visa-052",
    name: "Dependent 1 Year (Extend)",
    domain: "immigration",
    family: "dependent",
    route: "renewal",
    variant: "1 Year",
  },
  {
    id: "svc-visa-053",
    name: "Dependent 2 Years (Altus/Onshore)",
    domain: "immigration",
    family: "dependent",
    route: "onshore",
    variant: "2 Years",
  },
  {
    id: "svc-visa-054",
    name: "Dependent 2 Years (Offshore)",
    domain: "immigration",
    family: "dependent",
    route: "offshore",
    variant: "2 Years",
  },
  {
    id: "svc-visa-055",
    name: "Dependent 2 Years (Extend)",
    domain: "immigration",
    family: "dependent",
    route: "renewal",
    variant: "2 Years",
  },
  {
    id: "svc-visa-056",
    name: "Born KITAS",
    domain: "immigration",
    family: "born",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-057",
    name: "Retirement (Altus/Onshore)",
    domain: "immigration",
    family: "retirement",
    route: "onshore",
    variant: "",
  },
  {
    id: "svc-visa-058",
    name: "Retirement (Offshore)",
    domain: "immigration",
    family: "retirement",
    route: "offshore",
    variant: "",
  },
  {
    id: "svc-visa-059",
    name: "Retirement (Extend)",
    domain: "immigration",
    family: "retirement",
    route: "renewal",
    variant: "",
  },
  {
    id: "svc-visa-060",
    name: "Investor KITAP + MERP",
    domain: "immigration",
    family: "kitap-investor",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-061",
    name: "Dependent KITAP + MERP",
    domain: "immigration",
    family: "kitap-dependent",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-062",
    name: "Retirement KITAP + MERP",
    domain: "immigration",
    family: "kitap-retirement",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-063",
    name: "Reset Molina",
    domain: "immigration",
    family: "reset",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-064",
    name: "Created Molina Express",
    domain: "immigration",
    family: "create",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-065",
    name: "Passport 5 Years",
    domain: "immigration",
    family: "passport",
    route: "",
    variant: "5 Years",
  },
  {
    id: "svc-visa-066",
    name: "Passport 10 Years",
    domain: "immigration",
    family: "passport",
    route: "",
    variant: "10 Years",
  },
  {
    id: "svc-visa-067",
    name: "Electronic Passport 5 Years",
    domain: "immigration",
    family: "passport",
    route: "",
    variant: "5 Years",
  },
  {
    id: "svc-visa-068",
    name: "Electronic Passport 10 Years",
    domain: "immigration",
    family: "passport",
    route: "",
    variant: "10 Years",
  },
  {
    id: "svc-visa-069",
    name: "SKTT",
    domain: "immigration",
    family: "sktt",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-070",
    name: "SKCK",
    domain: "immigration",
    family: "skck",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-071",
    name: "Domicilie Letter",
    domain: "immigration",
    family: "domicile",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-072",
    name: "Mutation Passport",
    domain: "immigration",
    family: "mutation-passport",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-073",
    name: "Mutation Address",
    domain: "immigration",
    family: "mutation-address",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-074",
    name: "Mutation Address 2 Kanim",
    domain: "immigration",
    family: "mutation-transfer",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-075",
    name: "Lapor Lahir (Under)",
    domain: "immigration",
    family: "birth-under",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-076",
    name: "Lapor Lahir (Up)",
    domain: "immigration",
    family: "birth-up",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-077",
    name: "Cancel RPTKA",
    domain: "immigration",
    family: "cancel-rptka",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-078",
    name: "Cancel Wajib Lapor",
    domain: "immigration",
    family: "cancel-report",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-079",
    name: "Process IMTA & RPTKA Only (12 Months)",
    domain: "immigration",
    family: "labour",
    route: "",
    variant: "12 Months",
  },
  {
    id: "svc-visa-080",
    name: "Process IMTA & RPTKA Only (6 Months or Less)",
    domain: "immigration",
    family: "labour",
    route: "",
    variant: "6 Months or Less",
  },
  {
    id: "svc-visa-081",
    name: "EPO (Exit Permit Only)",
    domain: "immigration",
    family: "epo",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-082",
    name: "ERP (Exit Permit Only — Offshore)",
    domain: "immigration",
    family: "erp",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-083",
    name: "Driving License",
    domain: "immigration",
    family: "driving",
    route: "",
    variant: "",
  },
  {
    id: "svc-visa-084",
    name: "Urgent 1 Hari",
    domain: "immigration",
    family: "urgent",
    route: "",
    variant: "1-day target",
  },
  {
    id: "svc-visa-085",
    name: "Urgent 2 Hari",
    domain: "immigration",
    family: "urgent",
    route: "",
    variant: "2-day target",
  },
  {
    id: "svc-visa-086",
    name: "Urgent 3 Hari",
    domain: "immigration",
    family: "urgent",
    route: "",
    variant: "3-day target",
  },
  {
    id: "svc-company-001",
    name: "Company Revision",
    domain: "company-setup",
    family: "revision",
    route: "",
    variant: "",
  },
  {
    id: "svc-company-002",
    name: "SLHS (Hygiene Certificate)",
    domain: "company-setup",
    family: "slhs",
    route: "",
    variant: "",
  },
  {
    id: "svc-company-003",
    name: "Alcohol License (NPBBKC)",
    domain: "company-setup",
    family: "alcohol",
    route: "",
    variant: "",
  },
  {
    id: "svc-company-004",
    name: "PT PMA/PMDN Setup",
    domain: "company-setup",
    family: "formation",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-001",
    name: "NPWP Personal + Coretax",
    domain: "tax",
    family: "npwp",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-002",
    name: "NPWPD Corporate",
    domain: "tax",
    family: "npwpd",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-003",
    name: "SPT Annual Personal",
    domain: "tax",
    family: "personal-return",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-004",
    name: "SPT Annual Company (Zero)",
    domain: "tax",
    family: "zero-return",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-005",
    name: "SPT Annual Company (Operational)",
    domain: "tax",
    family: "operating-return",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-006",
    name: "Monthly Tax Report",
    domain: "tax",
    family: "monthly-tax",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-007",
    name: "BPJS Health Insurance",
    domain: "tax",
    family: "bpjs-health",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-008",
    name: "BPJS Employment Insurance",
    domain: "tax",
    family: "bpjs-employment",
    route: "",
    variant: "",
  },
  {
    id: "svc-tax-009",
    name: "LKPM Report",
    domain: "tax",
    family: "lkpm",
    route: "",
    variant: "",
  },
  {
    id: "svc-property-001",
    name: "Legal Due Diligence",
    domain: "property",
    family: "diligence",
    route: "",
    variant: "",
  },
  {
    id: "svc-property-002",
    name: "Leasehold Agreement (Hak Sewa)",
    domain: "property",
    family: "lease",
    route: "",
    variant: "",
  },
  {
    id: "svc-property-003",
    name: "Building Permits",
    domain: "property",
    family: "building",
    route: "",
    variant: "",
  },
  {
    id: "svc-property-004",
    name: "Ownership Structures (PT PMA)",
    domain: "property",
    family: "ownership",
    route: "",
    variant: "",
  },
] as const satisfies readonly DossierRecord[];

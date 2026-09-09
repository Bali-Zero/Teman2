/** People and roles carried forward from the reviewed R19 Team component.
 * Project responsibilities for Ari and Surya were supplied by the owner.
 * Do not expand these records into biographies without verified source material.
 */
export const founders = [
  { name: "Zainal Abidin", role: "Chief Executive Officer · Founder", image: "/assets/zainal-ceo.jpg" },
  { name: "Pak Heru", role: "Komisaris · Founder", image: "/assets/heru-komisaris.jpg" },
] as const;

export const boardMember = { name: "Ruslana", role: "Board Member", image: "/assets/ruslana.jpg" } as const;

export interface TeamMember {
  name: string;
  role: string;
  column: number;
  row: number;
  project?: { label: string; href: string };
}

// Coordinates select the existing portrait from the reviewed 4 × 4 image atlas.
export const teamMembers: readonly TeamMember[] = [
  { name: "Veronika", role: "Tax Manager", column: 1, row: 0 },
  { name: "Dewa Ayu", role: "Tax Consultant", column: 2, row: 0 },
  { name: "Krisna", role: "Setup Team", column: 3, row: 0 },
  { name: "Ari", role: "Second Home Studio", column: 0, row: 1, project: { label: "Explore Second Home Studio", href: "/#second-home-studio" } },
  { name: "Subhi", role: "Zantara · AI", column: 3, row: 1 },
  { name: "Adit", role: "Supervisor · Lead Setup", column: 0, row: 2 },
  { name: "Angel", role: "Tax Lead", column: 1, row: 2 },
  { name: "Candra", role: "Advisor · Ulu Team", column: 2, row: 2 },
  { name: "Vino", role: "Setup Team", column: 3, row: 2 },
  { name: "Asya", role: "Accounting", column: 0, row: 3 },
  { name: "Surya", role: "E-VOA", column: 1, row: 3, project: { label: "Explore E-VOA", href: "/#evoa" } },
  { name: "Damar", role: "Setup Team", column: 2, row: 3 },
  { name: "Dea", role: "Advisor · Ulu Team", column: 3, row: 3 },
];

/** Grouped from approved roles above, not the older page's wider roster. */
export const responsibilityGroups = [
  { id: "setup-advisory", title: "Setup & advisory", description: "Company setup, visa intake and the questions around getting established in Indonesia. Start here to discuss the scope of your next application or business project.", people: ["Adit", "Krisna", "Candra", "Vino", "Damar", "Dea"], link: { label: "Explore setup services", href: "/services/company-setup" } },
  { id: "tax", title: "Tax", description: "Personal and company tax questions, registration and reporting. Explore the service details to prepare for a conversation about your obligations.", people: ["Veronika", "Dewa Ayu", "Angel"], link: { label: "Explore tax services", href: "/services/tax" } },
  { id: "accounting", title: "Accounting", description: "Accounting support connects the records behind a business with its reporting needs. Contact the team to discuss the records and support your business requires.", people: ["Asya"], link: { label: "Discuss accounting support", href: "/contact?from=team&topic=tax" } },
  { id: "projects", title: "Projects & digital tools", description: "Ari is responsible for Second Home Studio, Surya for E-VOA, and Subhi works on Zantara. Explore each project's purpose before choosing your next step.", people: ["Ari", "Surya", "Subhi"], link: { label: "Explore our tools", href: "/#tools" } },
] as const;

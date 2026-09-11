// Exact service identities only; no amounts or price snapshots.
export const servicePriceIdentities: Readonly<
  Record<string, { key: string; category: string }>
> = {
  "A1 Visa-Free Tourism": {
    key: "A1 Visa-Free Tourism",
    category: "single_entry_visas",
  },
  "B1 Visa on Arrival (VOA)": {
    key: "B1 Visa on Arrival (VOA)",
    category: "single_entry_visas",
  },
  "B1 Visa on Arrival — Extension (+30 days)": {
    key: "B1 Visa on Arrival Extension",
    category: "single_entry_visas",
  },
  "C1 Tourism": {
    key: "C1 Tourism",
    category: "single_entry_visas",
  },
  "C1 Tourism — Extension (+60 days)": {
    key: "C1 Tourism Extension",
    category: "single_entry_visas",
  },
  "C2 Business": {
    key: "C2 Business",
    category: "single_entry_visas",
  },
  "C6 Social Activity": {
    key: "C6 Social Activity",
    category: "single_entry_visas",
  },
  "C7A,B,C — Music/Art": {
    key: "C7A,B,C Music/Art",
    category: "single_entry_visas",
  },
  "C8A,B Sports Events": {
    key: "C8A,B",
    category: "single_entry_visas",
  },
  "C10 Speaker Visa": {
    key: "C10 Speaker Visa",
    category: "single_entry_visas",
  },
  "C18 Work Trial": {
    key: "C18 Work Trial",
    category: "single_entry_visas",
  },
  "C22A&B Internship (60 Days)": {
    key: "C22A&B Internship (60 Days)",
    category: "single_entry_visas",
  },
  "C22A&B Internship (180 Days)": {
    key: "C22A&B Internship (180 Days)",
    category: "single_entry_visas",
  },
  "Bridging Visa": {
    key: "Bridging Visa",
    category: "single_entry_visas",
  },
  "D1 Tourism (1 Year)": {
    key: "D1 Tourism (1 Year)",
    category: "multiple_entry_visas",
  },
  "D1 Tourism (2 Years)": {
    key: "D1 Tourism (2 Years)",
    category: "multiple_entry_visas",
  },
  "D1 Tourism (5 Years)": {
    key: "D1 Tourism (5 Years)",
    category: "multiple_entry_visas",
  },
  "D2 Business (1 Year)": {
    key: "D2 Business (1 Year)",
    category: "multiple_entry_visas",
  },
  "D2 Business (2 Years)": {
    key: "D2 Business (2 Years)",
    category: "multiple_entry_visas",
  },
  "D12 Business Investigation (1 Year)": {
    key: "D12 Business Investigation (1 Year)",
    category: "multiple_entry_visas",
  },
  "D12 Business Investigation (2 Years)": {
    key: "D12 Business Investigation (2 Years)",
    category: "multiple_entry_visas",
  },
  "Working KITAS (Altus/Onshore)": {
    key: "Working KITAS (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Working KITAS (Offshore)": {
    key: "Working KITAS (Offshore)",
    category: "kitas_permits",
  },
  "Working KITAS (Extend)": {
    key: "Working KITAS (Extend)",
    category: "kitas_permits",
  },
  "Investor KITAS 2 Years (Altus/Onshore)": {
    key: "Investor KITAS 2 Years (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Investor KITAS 2 Years (Offshore)": {
    key: "Investor KITAS 2 Years (Offshore)",
    category: "kitas_permits",
  },
  "Investor KITAS 2 Years (Extend)": {
    key: "Investor KITAS 2 Years (Extend)",
    category: "kitas_permits",
  },
  "Freelance E23 (Altus/Onshore)": {
    key: "Freelance E23 (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Freelance E23 (Offshore)": {
    key: "Freelance E23 (Offshore)",
    category: "kitas_permits",
  },
  "E33G Remote Worker (Altus/Onshore)": {
    key: "E33G Remote Worker (Altus/Onshore)",
    category: "kitas_permits",
  },
  "E33G Remote Worker (Offshore)": {
    key: "E33G Remote Worker (Offshore)",
    category: "kitas_permits",
  },
  "E33G Remote Worker (Extend)": {
    key: "E33G Remote Worker (Extend)",
    category: "kitas_permits",
  },
  "E33 Second Home (5 Years)": {
    key: "E33 Second Home (5 Years)",
    category: "kitas_permits",
  },
  "E33E Second Home Senior (5 Years)": {
    key: "E33E Second Home Senior (5 Years)",
    category: "kitas_permits",
  },
  "E33E Second Home Senior (Extend)": {
    key: "E33E Second Home Senior (Extend)",
    category: "kitas_permits",
  },
  "E33F Second Home Senior (1 Year, Offshore)": {
    key: "E33F Second Home Senior (1 Year, Offshore)",
    category: "kitas_permits",
  },
  "E33F Second Home Senior (1 Year, Altus/Onshore)": {
    key: "E33F Second Home Senior (1 Year, Altus/Onshore)",
    category: "kitas_permits",
  },
  "E33F Second Home Senior (Extend)": {
    key: "E33F Second Home Senior (Extend)",
    category: "kitas_permits",
  },
  "E30A Education Visa (1 Year)": {
    key: "E30A Education Visa (1 Year)",
    category: "kitas_permits",
  },
  "E30A Education Visa (2 Years)": {
    key: "E30A Education Visa (2 Years)",
    category: "kitas_permits",
  },
  "E30B Higher Education (1 Year)": {
    key: "E30B Higher Education (1 Year)",
    category: "kitas_permits",
  },
  "E30B Higher Education (2 Years)": {
    key: "E30B Higher Education (2 Years)",
    category: "kitas_permits",
  },
  "E30B Higher Education (4 Years)": {
    key: "E30B Higher Education (4 Years)",
    category: "kitas_permits",
  },
  "Spouse 1 Year (Altus/Onshore)": {
    key: "Spouse 1 Year (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Spouse 1 Year (Offshore)": {
    key: "Spouse 1 Year (Offshore)",
    category: "kitas_permits",
  },
  "Spouse 1 Year (Extend)": {
    key: "Spouse 1 Year (Extend)",
    category: "kitas_permits",
  },
  "Spouse 2 Years (Altus/Onshore)": {
    key: "Spouse 2 Years (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Spouse 2 Years (Offshore)": {
    key: "Spouse 2 Years (Offshore)",
    category: "kitas_permits",
  },
  "Spouse 2 Years (Extend)": {
    key: "Spouse 2 Years (Extend)",
    category: "kitas_permits",
  },
  "Dependent 1 Year (Altus/Onshore)": {
    key: "Dependent 1 Year (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Dependent 1 Year (Offshore)": {
    key: "Dependent 1 Year (Offshore)",
    category: "kitas_permits",
  },
  "Dependent 1 Year (Extend)": {
    key: "Dependent 1 Year (Extend)",
    category: "kitas_permits",
  },
  "Dependent 2 Years (Altus/Onshore)": {
    key: "Dependent 2 Years (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Dependent 2 Years (Offshore)": {
    key: "Dependent 2 Years (Offshore)",
    category: "kitas_permits",
  },
  "Dependent 2 Years (Extend)": {
    key: "Dependent 2 Years (Extend)",
    category: "kitas_permits",
  },
  "Born KITAS": {
    key: "Born KITAS",
    category: "kitas_permits",
  },
  "Retirement (Altus/Onshore)": {
    key: "Retirement (Altus/Onshore)",
    category: "kitas_permits",
  },
  "Retirement (Offshore)": {
    key: "Retirement (Offshore)",
    category: "kitas_permits",
  },
  "Retirement (Extend)": {
    key: "Retirement (Extend)",
    category: "kitas_permits",
  },
  "Investor KITAP + MERP": {
    key: "Investor KITAP + MERP",
    category: "kitap_permits",
  },
  "Dependent KITAP + MERP": {
    key: "Dependent KITAP + MERP",
    category: "kitap_permits",
  },
  "Retirement KITAP + MERP": {
    key: "Retirement KITAP + MERP",
    category: "kitap_permits",
  },
  "Reset Molina": {
    key: "Reset Molina",
    category: "other_process",
  },
  "Created Molina Express": {
    key: "Created Molina Express",
    category: "other_process",
  },
  "Passport 5 Years": {
    key: "Passport 5 Years",
    category: "other_process",
  },
  "Passport 10 Years": {
    key: "Passport 10 Years",
    category: "other_process",
  },
  "Electronic Passport 5 Years": {
    key: "Electronic Passport 5 Years",
    category: "other_process",
  },
  "Electronic Passport 10 Years": {
    key: "Electronic Passport 10 Years",
    category: "other_process",
  },
  SKTT: {
    key: "SKTT",
    category: "other_process",
  },
  SKCK: {
    key: "SKCK",
    category: "other_process",
  },
  "Domicilie Letter": {
    key: "Domicilie Letter",
    category: "other_process",
  },
  "Mutation Passport": {
    key: "Mutation Passport",
    category: "other_process",
  },
  "Mutation Address": {
    key: "Mutation Address",
    category: "other_process",
  },
  "Mutation Address 2 Kanim": {
    key: "Mutation Address 2 Kanim",
    category: "other_process",
  },
  "Lapor Lahir (Under)": {
    key: "Lapor Lahir (Under)",
    category: "other_process",
  },
  "Lapor Lahir (Up)": {
    key: "Lapor Lahir (Up)",
    category: "other_process",
  },
  "Cancel RPTKA": {
    key: "Cancel RPTKA",
    category: "other_process",
  },
  "Cancel Wajib Lapor": {
    key: "Cancel Wajib Lapor",
    category: "other_process",
  },
  "Process IMTA & RPTKA Only (12 Months)": {
    key: "Process IMTA & RPTKA Only (12 Months)",
    category: "other_process",
  },
  "Process IMTA & RPTKA Only (6 Months or Less)": {
    key: "Process IMTA & RPTKA Only (6 Months or Less)",
    category: "other_process",
  },
  "EPO (Exit Permit Only)": {
    key: "EPO (Exit Permit Only)",
    category: "other_process",
  },
  "ERP (Exit Permit Only — Offshore)": {
    key: "ERP (Exit Re-entry Permit)",
    category: "other_process",
  },
  "Driving License": {
    key: "Driving License",
    category: "other_process",
  },
  "Urgent 1 Hari": {
    key: "Urgent 1 Hari",
    category: "urgent_processing",
  },
  "Urgent 2 Hari": {
    key: "Urgent 2 Hari",
    category: "urgent_processing",
  },
  "Urgent 3 Hari": {
    key: "Urgent 3 Hari",
    category: "urgent_processing",
  },
  "Compliance Takeover": {
    key: "compliance_takeover",
    category: "compliance_retainers",
  },
  "Core Compliance Retainer (Monthly)": {
    key: "compliance_core_retainer_monthly",
    category: "compliance_retainers",
  },
  "Employer Compliance Retainer (Monthly)": {
    key: "compliance_employer_retainer_monthly",
    category: "compliance_retainers",
  },
  "PSE Registration": {
    key: "pse_registration_fixed",
    category: "compliance_retainers",
  },
  "PMSE VAT Assessment": {
    key: "pmse_vat_assessment",
    category: "compliance_retainers",
  },
};

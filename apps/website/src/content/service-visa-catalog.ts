// Catalogue labels migrated from the existing public service source on 2026-09-08.
// Source: apps/mouth/data/bali-zero-prices.json, selected with the same exact-row
// filter as apps/mouth/src/data/services_data.ts. No amounts or price data copied.
// These labels identify services for quotation; they do not establish eligibility.
export const visaCatalog = [
  {
    "title": "Single-entry visits",
    "description": "Arriving, extending a visit, or travelling for a defined activity: these are different applications.",
    "services": [
      "A1 Visa-Free Tourism",
      "B1 Visa on Arrival (VOA)",
      "B1 Visa on Arrival — Extension (+30 days)",
      "C1 Tourism",
      "C1 Tourism — Extension (+60 days)",
      "C2 Business",
      "C6 Social Activity",
      "C7A,B,C — Music/Art",
      "C8A,B Sports Events",
      "C10 Speaker Visa",
      "C18 Work Trial",
      "C22A&B Internship (60 Days)",
      "C22A&B Internship (180 Days)",
      "Bridging Visa"
    ]
  },
  {
    "title": "Multiple-entry visits",
    "description": "Repeat visits have two clocks: the visa’s overall validity and the stay allowed on each entry.",
    "services": [
      "D1 Tourism (1 Year)",
      "D1 Tourism (2 Years)",
      "D1 Tourism (5 Years)",
      "D2 Business (1 Year)",
      "D2 Business (2 Years)",
      "D12 Business Investigation (1 Year)",
      "D12 Business Investigation (2 Years)"
    ]
  },
  {
    "title": "KITAS residence services",
    "description": "Start with the basis of residence, then distinguish a new entry, an onshore change and an existing-permit renewal.",
    "services": [
      "Working KITAS (Altus/Onshore)",
      "Working KITAS (Offshore)",
      "Working KITAS (Extend)",
      "Investor KITAS 2 Years (Altus/Onshore)",
      "Investor KITAS 2 Years (Offshore)",
      "Investor KITAS 2 Years (Extend)",
      "Freelance E23 (Altus/Onshore)",
      "Freelance E23 (Offshore)",
      "E33G Remote Worker (Altus/Onshore)",
      "E33G Remote Worker (Offshore)",
      "E33G Remote Worker (Extend)",
      "E33 Second Home (5 Years)",
      "E33E Second Home Senior (5 Years)",
      "E33E Second Home Senior (Extend)",
      "E33F Second Home Senior (1 Year, Offshore)",
      "E33F Second Home Senior (1 Year, Altus/Onshore)",
      "E33F Second Home Senior (Extend)",
      "E30A Education Visa (1 Year)",
      "E30A Education Visa (2 Years)",
      "E30B Higher Education (1 Year)",
      "E30B Higher Education (2 Years)",
      "E30B Higher Education (4 Years)",
      "Spouse 1 Year (Altus/Onshore)",
      "Spouse 1 Year (Offshore)",
      "Spouse 1 Year (Extend)",
      "Spouse 2 Years (Altus/Onshore)",
      "Spouse 2 Years (Offshore)",
      "Spouse 2 Years (Extend)",
      "Dependent 1 Year (Altus/Onshore)",
      "Dependent 1 Year (Offshore)",
      "Dependent 1 Year (Extend)",
      "Dependent 2 Years (Altus/Onshore)",
      "Dependent 2 Years (Offshore)",
      "Dependent 2 Years (Extend)",
      "Born KITAS",
      "Retirement (Altus/Onshore)",
      "Retirement (Offshore)",
      "Retirement (Extend)"
    ]
  },
  {
    "title": "KITAP services",
    "description": "Permanent-residence review starts with the qualifying history. Re-entry permission is a related, separate question.",
    "services": [
      "Investor KITAP + MERP",
      "Dependent KITAP + MERP",
      "Retirement KITAP + MERP"
    ]
  },
  {
    "title": "Documents & permit administration",
    "description": "Support for the administrative steps around a permit.",
    "services": [
      "Reset Molina",
      "Created Molina Express",
      "Passport 5 Years",
      "Passport 10 Years",
      "Electronic Passport 5 Years",
      "Electronic Passport 10 Years",
      "SKTT",
      "SKCK",
      "Domicilie Letter",
      "Mutation Passport",
      "Mutation Address",
      "Mutation Address 2 Kanim",
      "Lapor Lahir (Under)",
      "Lapor Lahir (Up)",
      "Cancel RPTKA",
      "Cancel Wajib Lapor",
      "Process IMTA & RPTKA Only (12 Months)",
      "Process IMTA & RPTKA Only (6 Months or Less)",
      "EPO (Exit Permit Only)",
      "ERP (Exit Permit Only — Offshore)",
      "Driving License"
    ]
  },
  {
    "title": "Urgent processing enquiries",
    "description": "Discuss availability and timing with the team before proceeding.",
    "services": [
      "Urgent 1 Hari",
      "Urgent 2 Hari",
      "Urgent 3 Hari"
    ]
  }
] as const;

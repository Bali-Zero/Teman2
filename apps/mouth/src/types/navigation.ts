// Navigation types for Zerosphere

export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: number;
  children?: NavItem[];
  roles?: string[]; // Role-based access
  external?: boolean; // Opens in new tab / external subdomain
}

export interface NavSection {
  title?: string;
  // One-line note rendered under the section title (e.g. an explanatory
  // subtitle). Currently only used by the owner-only "Da fare" section.
  note?: string;
  // When true, AppSidebar hides the whole section unless the signed-in
  // user is the owner (lib/auth/owner.ts::isOwner). Undefined/false means
  // visible to everyone, same as before this field existed.
  ownerOnly?: boolean;
  items: NavItem[];
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: string;
  team: string;
  avatar?: string;
  isOnline: boolean;
}

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

// Navigation configuration — Military-Grade 4-Block Layout
export const navigation: NavSection[] = [
  {
    // Block 1: Core
    items: [
      { title: "Dashboard", href: "/dashboard", icon: "Home" },
      { title: "Intelligence Center", href: "/intelligence", icon: "Activity" },
    ],
  },
  {
    title: "Work",
    // Block 2: Operations
    items: [
      { title: "Clients", href: "/clients", icon: "Users" },
      { title: "Process", href: "/process", icon: "FolderKanban" },
      { title: "Second Home", href: "/second-home", icon: "Home" },
      { title: "Review", href: "/review", icon: "ClipboardCheck" },
      { title: "Obligations", href: "/obligations", icon: "Receipt" },
      { title: "HR / Payroll", href: "/hr", icon: "Banknote" },
    ],
  },
  {
    title: "Kita-Space",
    // Block 3: Collaborative
    items: [
      { title: "LKPM", href: "/lkpm", icon: "ClipboardCheck" },
      { title: "Partners", href: "/partners", icon: "Handshake" },
      {
        title: "Email",
        // The Zoho mailbox itself. An existing Zoho session lands straight in
        // the inbox; without one, Zoho bounces through its login and returns
        // here via ?serviceurl=%2Fzm%2F.
        href: "https://mail.zoho.com/zm/",
        icon: "Mail",
        external: true,
      },
      {
        title: "Knowledge",
        href: "https://knowledge.balizero.com",
        icon: "BookOpen",
        external: true,
      },
    ],
  },
  {
    title: "System",
    // Block 4: Admin
    items: [{ title: "Settings", href: "/settings", icon: "Settings" }],
  },
  {
    title: "Da fare",
    note: "Pagine vive senza link — da rivedere",
    // Owner-only per Zero's 2026-09-12 ruling: these pages are live (real
    // data, no dead endpoints) but had zero inbound links anywhere in the
    // app before this section existed. Kept off the team sidebar until the
    // owner decides which stay, get merged elsewhere, or get cut.
    ownerOnly: true,
    items: [
      { title: "Accounting", href: "/accounting", icon: "Banknote" },
      {
        title: "Funnel Analytics",
        href: "/analytics/funnel",
        icon: "BarChart3",
      },
      { title: "GARUDA VOA", href: "/garuda-voa", icon: "ClipboardCheck" },
      {
        title: "Team Activity",
        href: "/admin/team-activity",
        icon: "Activity",
      },
      { title: "Agents", href: "/agents", icon: "BotMessageSquare" },
      {
        title: "Intelligence Analytics",
        href: "/intelligence/analytics",
        icon: "BarChart3",
      },
    ],
  },
];

// Portal navigation configuration
export const portalNavigation: NavSection[] = [
  {
    items: [
      { title: "Dashboard", href: "/portal", icon: "Home" },
      { title: "Process", href: "/portal/process", icon: "FolderOpen" },
      { title: "Vault", href: "/portal/vault", icon: "Archive" },
      { title: "Messages", href: "/portal/messages", icon: "MessageCircle" },
    ],
  },
  {
    title: "Services",
    items: [
      { title: "Companies", href: "/portal/companies", icon: "Building2" },
      { title: "Visa", href: "/portal/visa", icon: "Briefcase" },
      { title: "Taxes", href: "/portal/taxes", icon: "FileText" },
      { title: "LKPM", href: "/portal/lkpm", icon: "ClipboardCheck" },
      { title: "Billing", href: "/portal/billing", icon: "Receipt" },
    ],
  },
  {
    title: "Account",
    items: [
      { title: "Profile", href: "/portal/profile", icon: "UserCircle" },
      { title: "Family", href: "/portal/family", icon: "Users" },
      { title: "Settings", href: "/portal/settings", icon: "Settings" },
    ],
  },
];

export const partnerPortalNavigation: NavSection[] = [
  {
    items: [
      {
        title: "Dashboard",
        href: "/portal/partner/dashboard",
        icon: "Home",
      },
      {
        title: "Referrals",
        href: "/portal/partner/referrals",
        icon: "Users",
      },
      {
        title: "Commissions",
        href: "/portal/partner/commissions",
        icon: "Receipt",
      },
      {
        title: "Profile",
        href: "/portal/partner/profile",
        icon: "UserCircle",
      },
    ],
  },
];

// Route titles for breadcrumbs and page titles
export const routeTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/intelligence": "Intelligence Center",
  "/intelligence/visa-oracle": "Visa Oracle",
  "/intelligence/news-room": "News Room",
  "/chat": "Zantara AI",
  "/clients": "Clients",
  "/clients/new": "New Client",
  "/process": "Process",
  "/process/new": "New Process",
  "/second-home": "Second Home",
  "/second-home/new": "New Second Home Case",
  "/review": "Document Review",
  "/obligations": "Obligations",
  "/partners": "Partners",
  "/partners/new": "New Partner",
  "/hr": "HR / Payroll",
  "/hr/bonuses": "Bonuses",
  "/hr/payroll": "Payroll",
  "/hr/leave": "Leave Management",
  "/hr/leave/request": "Request Leave",
  "/hr/settings": "HR Settings",
  "/analytics/funnel": "Funnel Analytics",
  "/accounting": "Accounting",
  "/garuda-voa": "GARUDA VOA",
  "/admin/team-activity": "Team Activity",
  "/agents": "Agents",
  "/intelligence/analytics": "Intelligence Analytics",
  "/settings": "Settings",
  // Portal routes
  "/portal": "Dashboard",
  "/portal/process": "Process",
  "/portal/vault": "Vault",
  "/portal/messages": "Messages",
  "/portal/chat": "Messages",
  "/portal/companies": "Companies",
  "/portal/company": "Companies",
  "/portal/family": "Family",
  "/portal/matters": "Matters",
  "/portal/partner": "Partner",
  "/portal/visa": "Visa Status",
  "/portal/taxes": "Taxes",
  "/portal/profile": "Profile",
  "/portal/settings": "Settings",
  "/lkpm": "LKPM Reports",
  "/portal/lkpm": "Investment Reports",
  "/portal/billing": "Billing",
};

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
  clockedInAt?: string;
  hoursToday?: string;
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
      {
        title: "Zantara AI",
        href: "https://zantara.balizero.com",
        icon: "MessageSquare",
        external: true,
      },
    ],
  },
  {
    title: "Work",
    // Block 2: Operations
    items: [
      { title: "Clients", href: "/clients", icon: "Users" },
      { title: "Process", href: "/process", icon: "FolderKanban" },
      { title: "HR / Payroll", href: "/hr", icon: "Banknote" },
      { title: "LKPM", href: "/lkpm", icon: "ClipboardCheck" },
      {
        title: "Documents",
        href: "https://drive.balizero.com",
        icon: "FolderOpen",
        external: true,
      },
    ],
  },
  {
    title: "Kita-Space",
    // Block 3: Collaborative
    items: [
      {
        title: "Email",
        href: "https://mail.balizero.com",
        icon: "Mail",
        external: true,
      },
      {
        title: "Calendar",
        href: "https://calendar.balizero.com",
        icon: "Calendar",
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
];

// Portal navigation configuration
export const portalNavigation: NavSection[] = [
  {
    items: [
      { title: "Dashboard", href: "/portal", icon: "Home" },
      { title: "Process", href: "/portal/process", icon: "FolderOpen" },
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
    ],
  },
  {
    title: "Account",
    items: [
      { title: "Profile", href: "/portal/profile", icon: "UserCircle" },
      { title: "Settings", href: "/portal/settings", icon: "Settings" },
    ],
  },
];

// Route titles for breadcrumbs and page titles
export const routeTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/intelligence": "Intelligence Center",
  "/intelligence/visa-oracle": "Visa Oracle",
  "/intelligence/news-room": "News Room",
  "/intelligence/system-pulse": "System Pulse",
  "/chat": "Zantara AI",
  "/whatsapp": "WhatsApp",
  "/clients": "Clients",
  "/clients/new": "New Client",
  "/process": "Process",
  "/process/new": "New Process",
  "/process/deadlines": "Deadlines",
  "/documents": "Documents (Drive)",
  "/knowledge": "Knowledge Base",
  "/team": "Team",
  "/team/timesheet": "Timesheet",
  "/team/calendar": "Team Calendar",
  "/calendar": "Bali Zero Calendar",
  "/hr": "HR / Payroll",
  "/hr/bonuses": "Bonuses",
  "/hr/payroll": "Payroll",
  "/hr/leave": "Leave Management",
  "/hr/leave/request": "Request Leave",
  "/hr/settings": "HR Settings",
  "/analytics": "Analytics",
  "/settings": "Settings",
  "/settings/users": "User Management",
  "/dream": "Dream Room",
  // Portal routes
  "/portal": "Dashboard",
  "/portal/vault": "Vault",
  "/portal/messages": "Messages",
  "/portal/visa": "Visa Status",
  "/portal/taxes": "Taxes",
  "/portal/profile": "Profile",
  "/portal/settings": "Settings",
  "/lkpm": "LKPM Reports",
  "/portal/lkpm": "Investment Reports",
};

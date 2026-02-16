// Navigation types for Zerosphere

export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: number;
  children?: NavItem[];
  roles?: string[]; // Role-based access
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

// Navigation configuration
export const navigation: NavSection[] = [
  {
    items: [
      { title: "Dashboard", href: "/dashboard", icon: "Home" },
      { title: "Intelligence Center", href: "/intelligence", icon: "Activity" },
      { title: "Zantara AI", href: "/chat", icon: "MessageSquare" },
      { title: "Dream Room", href: "/dream", icon: "Cloud" },
      { title: "Omnichannel", href: "/omnichannel", icon: "MessageCircle" },
      { title: "Email", href: "/email", icon: "Mail" },
    ],
  },
  {
    title: "Work",
    items: [
      { title: "Clients", href: "/clients", icon: "Users" },
      { title: "Process", href: "/process", icon: "FolderKanban" },
      { title: "Documents", href: "/documents", icon: "FolderOpen" },
      { title: "Knowledge", href: "/knowledge", icon: "BookOpen" },
    ],
  },
  {
    title: "Team",
    items: [
      { title: "Team", href: "/team", icon: "UserCircle" },
      { title: "Calendar", href: "/calendar", icon: "Calendar" },
      { title: "Analytics", href: "/analytics", icon: "BarChart3" },
    ],
  },
  {
    title: "System",
    items: [{ title: "Settings", href: "/settings", icon: "Settings" }],
  },
];

// Portal navigation configuration
export const portalNavigation: NavSection[] = [
  {
    items: [
      { title: "Dashboard", href: "/portal", icon: "Home" },
      { title: "Vault", href: "/portal/vault", icon: "FolderOpen" },
      { title: "Messages", href: "/portal/messages", icon: "MessageCircle" },
    ],
  },
  {
    title: "Services",
    items: [
      { title: "Visa", href: "/portal/visa", icon: "Briefcase" },
      { title: "Taxes", href: "/portal/taxes", icon: "FileText" },
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
  "/omnichannel": "Omnichannel",
  "/whatsapp": "WhatsApp",
  "/email": "Email",
  "/clients": "Clients",
  "/clients/new": "New Client",
  "/process": "Process",
  "/process/new": "New Process",
  "/process/deadlines": "Deadlines",
  "/documents": "Documents",
  "/knowledge": "Knowledge Base",
  "/team": "Team",
  "/team/timesheet": "Timesheet",
  "/team/calendar": "Team Calendar",
  "/calendar": "Bali Zero Calendar",
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
};

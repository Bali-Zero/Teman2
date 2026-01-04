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
      { title: 'Dashboard', href: '/dashboard', icon: 'Home' },
      { title: 'Intelligence Center', href: '/intelligence', icon: 'Activity' },
      { title: 'Zantara AI', href: '/chat', icon: 'MessageSquare' },
      { title: 'WhatsApp', href: '/whatsapp', icon: 'MessageCircle' },
      { title: 'Email', href: '/email', icon: 'Mail' },
    ],
  },
  {
    title: 'Work',
    items: [
      { title: 'Clients', href: '/clients', icon: 'Users' },
      { title: 'Cases', href: '/cases', icon: 'FolderKanban' },
      { title: 'Documents', href: '/documents', icon: 'FolderOpen' },
      { title: 'Knowledge', href: '/knowledge', icon: 'BookOpen' },
    ],
  },
  {
    title: 'Team',
    items: [
      { title: 'Team', href: '/team', icon: 'UserCircle' },
      { title: 'Analytics', href: '/analytics', icon: 'BarChart3' },
    ],
  },
  {
    title: 'System',
    items: [
      { title: 'Settings', href: '/settings', icon: 'Settings' },
    ],
  },
];

// Route titles for breadcrumbs and page titles
export const routeTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/intelligence': 'Intelligence Center',
  '/intelligence/visa-oracle': 'Visa Oracle',
  '/intelligence/news-room': 'News Room',
  '/intelligence/system-pulse': 'System Pulse',
  '/chat': 'Zantara AI',
  '/whatsapp': 'WhatsApp',
  '/email': 'Email',
  '/clients': 'Clients',
  '/clients/new': 'New Client',
  '/cases': 'Cases',
  '/cases/new': 'New Case',
  '/cases/deadlines': 'Deadlines',
  '/documents': 'Documents',
  '/knowledge': 'Knowledge Base',
  '/team': 'Team',
  '/team/timesheet': 'Timesheet',
  '/team/calendar': 'Calendar',
  '/analytics': 'Analytics',
  '/settings': 'Settings',
  '/settings/users': 'User Management',
};

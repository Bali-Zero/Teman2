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
      { title: 'Zantara AI', href: '/chat', icon: 'MessageSquare' },
      { title: 'WhatsApp', href: '/whatsapp', icon: 'MessageCircle' },
    ],
  },
  {
    title: 'Lavoro',
    items: [
      { title: 'Clienti', href: '/clienti', icon: 'Users' },
      { title: 'Pratiche', href: '/pratiche', icon: 'FolderKanban' },
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
    title: 'Sistema',
    items: [
      { title: 'Settings', href: '/settings', icon: 'Settings' },
    ],
  },
];

// Route titles for breadcrumbs and page titles
export const routeTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/chat': 'Zantara AI',
  '/whatsapp': 'WhatsApp',
  '/clienti': 'Clienti',
  '/clienti/nuovo': 'Nuovo Cliente',
  '/pratiche': 'Pratiche',
  '/pratiche/nuova': 'Nuova Pratica',
  '/pratiche/scadenze': 'Scadenze',
  '/knowledge': 'Knowledge Base',
  '/team': 'Team',
  '/team/timesheet': 'Timesheet',
  '/team/calendar': 'Calendario',
  '/analytics': 'Analytics',
  '/settings': 'Impostazioni',
  '/settings/users': 'Gestione Utenti',
};

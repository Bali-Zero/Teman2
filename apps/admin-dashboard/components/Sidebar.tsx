"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Database,
  FolderTree,
  Home,
  Sparkles,
  Network,
  Activity,
  UserCog,
  Scale,
  Calendar,
} from "lucide-react";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();

  const links = [
    { href: "/", label: "Overview", icon: Home },
    { href: "/postgres", label: "PostgreSQL", icon: Database },
    { href: "/qdrant", label: "Qdrant", icon: FolderTree },
    { href: "/rag", label: "RAG Playground", icon: Sparkles },
    { href: "/knowledge-graph", label: "Knowledge Graph", icon: Network },
    { href: "/legal", label: "Legal Documents", icon: Scale },
    { href: "/calendar", label: "Bali Zero Calendar", icon: Calendar },
    { href: "/activity", label: "Agent Activity", icon: Activity },
    { href: "/users", label: "User Context", icon: UserCog },
  ];

  return (
    <div className="w-64 border-r h-screen bg-muted/20 flex flex-col fixed left-0 top-0">
      <div className="p-6 border-b">
        <h1 className="font-bold text-xl tracking-tight">Nuzantara Admin</h1>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive =
            pathname === link.href ||
            (link.href !== "/" && pathname.startsWith(link.href));
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md transition-colors text-sm font-medium",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon size={18} />
              {link.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t text-xs text-muted-foreground">
        System Engine
      </div>
    </div>
  );
}

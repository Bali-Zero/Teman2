"use client";
import Image from "next/image";
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

  const items = links.map((link) => {
    const Icon = link.icon;
    const isActive =
      pathname === link.href ||
      (link.href !== "/" && pathname.startsWith(link.href));

    return { ...link, Icon, isActive };
  });

  return (
    <>
      <div className="sticky top-0 z-40 border-b bg-background/95 lg:hidden">
        <div className="px-4 py-3">
          <div className="flex items-center gap-2">
            <Image
              src="/autonomous-lab-logo.png"
              alt="Nuzantara logo"
              width={34}
              height={34}
              className="h-8 w-8 rounded-md object-contain"
              priority
            />
            <div className="text-lg font-bold tracking-tight">
              Nuzantara Admin
            </div>
          </div>
        </div>
        <nav
          aria-label="Admin sections"
          className="flex max-w-full gap-1.5 overflow-x-auto overscroll-x-contain px-2 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {items.map(({ href, label, Icon, isActive }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-2 text-xs font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon size={15} />
              <span className="whitespace-nowrap">{label}</span>
            </Link>
          ))}
        </nav>
      </div>

      <div className="fixed left-0 top-0 hidden h-screen w-64 flex-col border-r bg-muted/20 lg:flex">
        <div className="border-b p-6">
          <div className="flex items-center gap-3">
            <Image
              src="/autonomous-lab-logo.png"
              alt="Nuzantara logo"
              width={42}
              height={42}
              className="h-10 w-10 rounded-md object-contain"
              priority
            />
            <div>
              <div className="text-xl font-bold tracking-tight">
                Nuzantara Admin
              </div>
              <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Lab Console
              </div>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-2 p-4">
          {items.map(({ href, label, Icon, isActive }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2 border-t p-4 text-xs text-muted-foreground">
          <Image
            src="/autonomous-lab-logo.png"
            alt=""
            width={22}
            height={22}
            className="h-5 w-5 rounded-sm object-contain opacity-70"
          />
          <span>System Engine</span>
        </div>
      </div>
    </>
  );
}

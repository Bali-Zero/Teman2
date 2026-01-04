import Link from "next/link";
import { cn } from "@/lib/utils";

const tabs = [
  { name: "Visa Oracle", href: "/intelligence/visa-oracle", icon: "🛂" },
  { name: "News Room", href: "/intelligence/news-room", icon: "📰" },
  { name: "System Pulse", href: "/intelligence/system-pulse", icon: "💓" },
];

export default function IntelligenceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex flex-col space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Intelligence Center</h1>
        <p className="text-muted-foreground">
          Manage automated intelligence gathering and knowledge base updates.
        </p>
      </div>
      
      <div className="border-b">
        <div className="flex h-10 items-center space-x-4">
          {tabs.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex items-center text-sm font-medium transition-colors hover:text-primary",
                "text-muted-foreground" // Active state would need client component check
              )}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.name}
            </Link>
          ))}
        </div>
      </div>
      
      <div className="flex-1">
        {children}
      </div>
    </div>
  );
}
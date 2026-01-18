"use client";
import { useState, useEffect } from 'react';
import { Card, CardContent, Badge } from '@/components/ui/primitives';
import { Database, Search, Layers, Shield, Users, FileText, Activity } from 'lucide-react';
import Link from 'next/link';

// Define categories
const CATEGORIES: Record<string, { label: string; icon: any; match: (name: string) => boolean }> = {
  crm: { 
    label: 'CRM & Clients', 
    icon: Users, 
    match: (n) => n.includes('client') || n.includes('user') || n.includes('contact') 
  },
  ops: { 
    label: 'Operations & Work', 
    icon: Activity, 
    match: (n) => n.includes('practice') || n.includes('conversation') || n.includes('interaction') || n.includes('work_hours') || n.includes('rating')
  },
  knowledge: { 
    label: 'Knowledge & RAG', 
    icon: FileText, 
    match: (n) => n.includes('document') || n.includes('kbli') || n.includes('golden') || n.includes('memor') || n.includes('folder')
  },
  system: { 
    label: 'System & Logs', 
    icon: Shield, 
    match: (n) => n.includes('log') || n.includes('audit') || n.includes('token') || n.includes('setting') || n.includes('job')
  }
};

export default function PostgresPage() {
  const [tables, setTables] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch('/api/postgres/tables')
      .then(res => res.json())
      .then(data => {
        if (data.tables) setTables(data.tables);
      })
      .finally(() => setLoading(false));
  }, []);

  const filteredTables = tables.filter(t => t.table_name.toLowerCase().includes(search.toLowerCase()));

  // Group tables
  const grouped: Record<string, typeof tables> = {
    crm: [],
    ops: [],
    knowledge: [],
    system: [],
    other: []
  };

  filteredTables.forEach(table => {
    const name = table.table_name.toLowerCase();
    if (CATEGORIES.crm.match(name)) grouped.crm.push(table);
    else if (CATEGORIES.ops.match(name)) grouped.ops.push(table);
    else if (CATEGORIES.knowledge.match(name)) grouped.knowledge.push(table);
    else if (CATEGORIES.system.match(name)) grouped.system.push(table);
    else grouped.other.push(table);
  });

  const sections = [
    { key: 'crm', ...CATEGORIES.crm },
    { key: 'ops', ...CATEGORIES.ops },
    { key: 'knowledge', ...CATEGORIES.knowledge },
    { key: 'system', ...CATEGORIES.system },
    { key: 'other', label: 'Other Tables', icon: Database, match: () => true }
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">PostgreSQL Tables</h1>
          <p className="text-muted-foreground">Browsable tables from the <code>public</code> schema.</p>
        </div>
        <div className="relative w-[300px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <input 
            className="w-full bg-background border rounded-md pl-9 pr-4 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
            placeholder="Search tables..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-muted-foreground">Loading schema metadata...</div>
      ) : (
        <div className="space-y-10">
          {sections.map(section => {
            const sectionTables = grouped[section.key];
            if (sectionTables.length === 0) return null;

            return (
              <div key={section.key} className="space-y-4">
                <div className="flex items-center gap-2 border-b pb-2">
                  <section.icon className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold">{section.label}</h2>
                  <Badge variant="secondary" className="ml-2">{sectionTables.length}</Badge>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {sectionTables.map((table: any) => (
                    <Link key={table.table_name} href={`/postgres/${table.table_name}`} className="block group">
                      <Card className="hover:border-primary/50 transition-colors h-full">
                        <CardContent className="p-4 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Database className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                            <span className="font-medium truncate max-w-[180px]" title={table.table_name}>
                              {table.table_name}
                            </span>
                          </div>
                          <Badge variant="outline" className="text-xs font-mono">
                            {parseInt(table.row_count) > 1000 ? `${(parseInt(table.row_count)/1000).toFixed(1)}k` : table.row_count} rows
                          </Badge>
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

"use client";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardTitle, Badge } from '@/components/ui/primitives';
import { Database, Search } from 'lucide-react';

export default function PostgresPage() {
  const [tables, setTables] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetch('/api/postgres/tables')
      .then(res => res.json())
      .then(data => {
        if (data.tables) setTables(data.tables);
        setLoading(false);
      })
      .catch(err => setLoading(false));
  }, []);

  const filtered = tables.filter(t => t.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
           <h1 className="text-3xl font-bold tracking-tight">PostgreSQL Tables</h1>
           <p className="text-muted-foreground">Select a table to inspect its data.</p>
        </div>
        <div className="relative w-64">
           <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
           <input 
             placeholder="Search tables..." 
             className="w-full pl-8 h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
             value={search}
             onChange={e => setSearch(e.target.value)}
           />
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20">Loading tables...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((table) => (
            <Link key={table.name} href={`/postgres/${table.name}`}>
              <Card className="hover:bg-muted/5 transition-colors cursor-pointer border-l-4 border-l-primary/10 hover:border-l-primary h-full">
                <CardContent className="p-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-full">
                      <Database className="h-4 w-4 text-primary" />
                    </div>
                    <span className="font-medium truncate max-w-[180px]" title={table.name}>{table.name}</span>
                  </div>
                  <Badge variant="secondary">{table.count} rows</Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

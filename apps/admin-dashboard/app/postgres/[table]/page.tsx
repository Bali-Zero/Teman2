"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button, Badge } from "@/components/ui/primitives";
import { ArrowLeft, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";

export default function TableDataPage({
  params,
}: {
  params: { table: string };
}) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [columns, setColumns] = useState<string[]>([]);

  const fetchData = (p: number) => {
    setLoading(true);
    fetch(`/api/postgres/query?table=${params.table}&page=${p}`)
      .then((res) => res.json())
      .then((res) => {
        if (res.rows) {
          setData(res.rows);
          if (res.rows.length > 0) {
            setColumns(Object.keys(res.rows[0]));
          }
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchData(page);
  }, [page]);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Header */}
      <div className="border-b p-4 flex items-center justify-between bg-background z-10">
        <div className="flex items-center gap-4">
          <Link href="/postgres">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
              {params.table}
              <Badge
                variant="outline"
                className="font-normal text-muted-foreground"
              >
                {data.length} rows visible
              </Badge>
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fetchData(page)}>
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
          <div className="flex items-center gap-1 border rounded-md">
            <Button
              variant="ghost"
              size="icon"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm px-2 min-w-[3rem] text-center">
              Pg {page}
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Loading data...
          </div>
        ) : data.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            No records found.
          </div>
        ) : (
          <div className="rounded-md border relative">
            <div className="overflow-x-auto">
              <table className="w-full caption-bottom text-sm text-left">
                <thead className="[&_tr]:border-b bg-muted/50 sticky top-0 z-20 shadow-sm">
                  <tr className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                    {columns.map((col) => (
                      <th
                        key={col}
                        className="h-10 px-4 text-left align-middle font-medium text-muted-foreground whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="[&_tr:last-child]:border-0 divide-y">
                  {data.map((row, i) => (
                    <tr
                      key={i}
                      className="border-b transition-colors hover:bg-muted/50"
                    >
                      {columns.map((col) => (
                        <td
                          key={`${i}-${col}`}
                          className="p-4 align-middle whitespace-nowrap max-w-[300px] overflow-hidden text-ellipsis"
                        >
                          {typeof row[col] === "object"
                            ? JSON.stringify(row[col])
                            : String(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { TableDataResponse } from '@/lib/api/admin/admin.types';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { RefreshCw, Database, ChevronLeft, ChevronRight } from 'lucide-react';

export function DbExplorer() {
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [tableData, setTableData] = useState<TableDataResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  useEffect(() => {
    loadTables();
  }, []);

  const loadTables = async () => {
    try {
      const data = await api.getPostgresTables();
      setTables(data);
      if (data.length > 0 && !selectedTable) {
        // Don't auto-select, let user choose
      }
    } catch (err) {
      console.error('Failed to load tables', err);
    }
  };

  const loadData = async (table: string, newPage: number) => {
    setIsLoading(true);
    try {
      const offset = newPage * PAGE_SIZE;
      const data = await api.getTableData(table, PAGE_SIZE, offset);
      setTableData(data);
      setPage(newPage);
    } catch (err) {
      console.error('Failed to load data', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTableChange = (value: string) => {
    setSelectedTable(value);
    setPage(0);
    loadData(value, 0);
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-4 bg-black/40 p-4 rounded-lg border border-white/10">
        <Database className="text-blue-500 w-5 h-5" />
        <Select value={selectedTable} onValueChange={handleTableChange}>
          <SelectTrigger className="w-[300px] bg-black border-white/20 text-white">
            <SelectValue placeholder="Select Table" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-800 text-white">
            {tables.map((t) => (
              <SelectItem key={t} value={t} className="focus:bg-zinc-800 focus:text-white cursor-pointer">
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="icon"
          onClick={() => selectedTable && loadData(selectedTable, page)}
          className="ml-auto"
          disabled={!selectedTable || isLoading}
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Data Grid */}
      {tableData ? (
        <div className="border border-white/10 rounded-lg overflow-hidden bg-black/20">
          <div className="p-2 bg-white/5 border-b border-white/10 flex justify-between items-center text-xs text-muted-foreground">
            <span>
              Rows {page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, tableData.total_rows)} of {tableData.total_rows}
            </span>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => loadData(selectedTable, page - 1)}
                disabled={page === 0 || isLoading}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => loadData(selectedTable, page + 1)}
                disabled={(page + 1) * PAGE_SIZE >= tableData.total_rows || isLoading}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent border-white/10">
                  {tableData.columns.map((col) => (
                    <TableHead key={col} className="text-blue-400 font-mono text-xs whitespace-nowrap">
                      {col}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {tableData.rows.length === 0 ? (
                    <TableRow>
                        <TableCell colSpan={tableData.columns.length} className="text-center h-24 text-muted-foreground">
                            No data found
                        </TableCell>
                    </TableRow>
                ) : (
                    tableData.rows.map((row, i) => (
                    <TableRow key={i} className="hover:bg-white/5 border-white/5">
                        {tableData.columns.map((col) => {
                            const val = row[col];
                            return (
                                <TableCell key={`${i}-${col}`} className="font-mono text-xs max-w-[200px] truncate text-zinc-300">
                                    {val === null ? <span className="text-zinc-600">NULL</span> : String(val)}
                                </TableCell>
                            );
                        })}
                    </TableRow>
                    ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      ) : (
        <div className="h-[400px] flex items-center justify-center border border-white/5 rounded-lg border-dashed text-muted-foreground">
          Select a table to inspect data
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { api } from "@/lib/api";
import type { Job } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const col = createColumnHelper<Job>();

const columns = [
  col.accessor("title", { header: "Title" }),
  col.accessor("company", { header: "Company" }),
  col.accessor("location", { header: "Location", cell: (i) => i.getValue() ?? "—" }),
  col.accessor("final_score", {
    header: "Score",
    cell: (i) => {
      const v = i.getValue();
      return v != null ? (v * 100).toFixed(0) : "—";
    },
  }),
  col.accessor("company_tier", { header: "Tier", cell: (i) => i.getValue() ?? "—" }),
  col.accessor("is_contract", {
    header: "Contract",
    cell: (i) => (i.getValue() ? <Badge variant="outline">Contract</Badge> : null),
  }),
  col.accessor("site", { header: "Site", cell: (i) => i.getValue() ?? "—" }),
  col.display({
    id: "link",
    header: "",
    cell: (i) => (
      <a
        href={i.row.original.job_url}
        target="_blank"
        rel="noreferrer"
        className="text-xs underline"
      >
        Open
      </a>
    ),
  }),
];

export default function JobsPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";

  const [jobs, setJobs] = useState<Job[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [sorting, setSorting] = useState<SortingState>([]);
  const limit = 50;

  useEffect(() => {
    if (!token) return;
    api.jobs.list(token, page, limit).then((r) => {
      setJobs(r.jobs);
      setTotal(r.total);
    });
  }, [token, page]);

  const table = useReactTable({
    data: jobs,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Jobs ({total})</h1>
        <a href="/dashboard" className="text-sm underline">Dashboard</a>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => (
                  <TableHead
                    key={h.id}
                    className="cursor-pointer select-none"
                    onClick={h.column.getToggleSortingHandler()}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {h.column.getIsSorted() === "asc" ? " ↑" : h.column.getIsSorted() === "desc" ? " ↓" : ""}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          Previous
        </Button>
        <span className="text-sm text-muted-foreground">
          Page {page} of {Math.ceil(total / limit) || 1}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setPage((p) => p + 1)}
          disabled={page * limit >= total}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

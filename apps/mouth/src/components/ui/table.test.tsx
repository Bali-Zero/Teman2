import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
} from "./table";

describe("Table", () => {
  it("renders a table element inside a scroll wrapper", () => {
    render(
      <Table>
        <TableBody>
          <TableRow>
            <TableCell>Cell</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("forwards ref to the table element", () => {
    const ref = React.createRef<HTMLTableElement>();
    render(
      <Table ref={ref}>
        <TableBody>
          <TableRow>
            <TableCell>Cell</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(ref.current).toBeInstanceOf(HTMLTableElement);
  });
});

describe("Table composition", () => {
  it("renders a complete table with header, body, and caption", () => {
    render(
      <Table>
        <TableCaption>A list of invoices</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>John</TableCell>
            <TableCell>$100</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Jane</TableCell>
            <TableCell>$200</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    expect(screen.getByText("A list of invoices")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("John")).toBeInTheDocument();
    expect(screen.getByText("$200")).toBeInTheDocument();
  });

  it("applies custom className to all sub-components", () => {
    const { container } = render(
      <Table className="my-table">
        <TableHeader className="my-header">
          <TableRow className="my-row">
            <TableHead className="my-head">H</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody className="my-body">
          <TableRow>
            <TableCell className="my-cell">C</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    expect(container.querySelector(".my-table")).toBeTruthy();
    expect(container.querySelector(".my-header")).toBeTruthy();
    expect(container.querySelector(".my-row")).toBeTruthy();
    expect(container.querySelector(".my-head")).toBeTruthy();
    expect(container.querySelector(".my-body")).toBeTruthy();
    expect(container.querySelector(".my-cell")).toBeTruthy();
  });
});

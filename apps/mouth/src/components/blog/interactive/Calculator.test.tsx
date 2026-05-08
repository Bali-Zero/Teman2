import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { Calculator, type CalculatorField } from "./Calculator";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    info: vi.fn(),
  },
}));

describe("Calculator", () => {
  const fields: CalculatorField[] = [
    {
      id: "employees",
      label: "Employees",
      type: "number",
      defaultValue: 2,
      unit: "people",
    },
    {
      id: "term",
      label: "Term",
      type: "slider",
      min: 1,
      max: 12,
      defaultValue: 6,
      unit: "months",
    },
    {
      id: "package",
      label: "Package",
      type: "select",
      options: [
        { value: "starter", label: "Starter" },
        { value: "prime", label: "Prime" },
      ],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts empty, then renders formatted breakdown and total after input changes", () => {
    const calculate = vi.fn((values: Record<string, number | string | boolean>) => {
      const employees = Number(values.employees);
      const term = Number(values.term);
      const multiplier = values.package === "prime" ? 2 : 1;

      return [
        {
          label: "Base",
          value: employees * 1000000 * multiplier,
          format: "currency" as const,
          description: "Per employee",
        },
        {
          label: "Term weight",
          value: term / 100,
          format: "percentage" as const,
          highlight: true,
        },
        {
          label: "Estimated total",
          value: employees * term * 1000000 * multiplier,
          format: "currency" as const,
          isTotal: true,
        },
      ];
    });

    render(
      <Calculator
        id="cost"
        title="Cost Estimator"
        fields={fields}
        calculate={calculate}
        disclaimer="Indicative only."
      />,
    );

    expect(screen.getByText("Adjust the parameters to see estimated costs")).toBeInTheDocument();
    expect(screen.getByText("Indicative only.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Employees"), {
      target: { value: "3" },
    });

    expect(screen.getByText("Base")).toBeInTheDocument();
    expect(screen.getByText("Term weight")).toBeInTheDocument();
    expect(screen.getByText("Estimated total")).toBeInTheDocument();
    expect(screen.getByText("Rp 3.000.000")).toBeInTheDocument();
    expect(screen.getByText("0.1%")).toBeInTheDocument();
    expect(screen.getByText("Rp 18.000.000")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "prime" },
    });

    expect(screen.getByText("Rp 6.000.000")).toBeInTheDocument();
  });

  it("resets values and exposes the download toast action", () => {
    render(
      <Calculator
        id="cost"
        title="Cost Estimator"
        fields={fields}
        calculate={() => [
          {
            label: "Estimated total",
            value: 1200,
            format: "number",
            isTotal: true,
          },
        ]}
        allowDownload
      />,
    );

    fireEvent.change(screen.getByLabelText("Employees"), {
      target: { value: "4" },
    });
    expect(screen.getByText("1,200")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /reset calculator/i }));
    expect(screen.getByText("Adjust the parameters to see estimated costs")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Employees"), {
      target: { value: "5" },
    });
    fireEvent.click(screen.getByRole("button", { name: /download estimate/i }));

    expect(toast.info).toHaveBeenCalledWith(
      "Coming soon",
      expect.objectContaining({
        description: expect.stringContaining("PDF download"),
      }),
    );
  });
});

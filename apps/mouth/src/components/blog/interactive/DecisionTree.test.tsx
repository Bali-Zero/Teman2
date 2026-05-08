import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionTree, type DecisionNode } from "./DecisionTree";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    button: ({
      children,
      ...props
    }: React.PropsWithChildren<Record<string, unknown>>) => (
      <button {...props}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

describe("DecisionTree", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  const nodes: DecisionNode[] = [
    {
      id: "start",
      question: "What is the client entity type?",
      description: "Choose the closest operating structure.",
      options: [
        {
          label: "PT PMA",
          description: "Foreign-owned company",
          nextNodeId: "pma",
        },
        {
          label: "Local PT",
          nextNodeId: "local",
        },
      ],
    },
    {
      id: "pma",
      question: "Does the KBLI allow foreign ownership?",
      options: [{ label: "Yes", nextNodeId: "result-prime" }],
    },
    {
      id: "local",
      question: "Local result",
      isResult: true,
      options: [],
      result: {
        title: "Use local compliance path",
        description: "Keep the ownership flow domestic.",
      },
    },
    {
      id: "result-prime",
      question: "Prime result",
      isResult: true,
      options: [],
      result: {
        title: "Proceed with PMA review",
        description: "Run PMA eligibility and document checks.",
        color: "green",
        learnMoreUrl: "/kbli/pma",
        learnMoreLabel: "Open PMA guide",
        recommendations: ["Verify DNI status", "Check minimum capital"],
        nextSteps: ["Collect NIB", "Prepare OSS submission"],
      },
    },
  ];

  it("walks a path to a result and reports completion", () => {
    vi.useFakeTimers();
    const onComplete = vi.fn();
    render(
      <DecisionTree
        title="Entity Router"
        subtitle="Find the right compliance path"
        nodes={nodes}
        onComplete={onComplete}
      />,
    );

    expect(screen.getByText("Entity Router")).toBeInTheDocument();
    expect(screen.getByText("What is the client entity type?")).toBeInTheDocument();
    expect(screen.getByText("0%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /pt pma/i }));
    expect(screen.getByText("Does the KBLI allow foreign ownership?")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(300);
    });

    fireEvent.click(screen.getByRole("button", { name: /^yes/i }));

    expect(screen.getByText("Proceed with PMA review")).toBeInTheDocument();
    expect(screen.getByText("Verify DNI status")).toBeInTheDocument();
    expect(screen.getByText("Collect NIB")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open pma guide/i })).toHaveAttribute(
      "href",
      "/kbli/pma",
    );
    expect(onComplete).toHaveBeenCalledWith("result-prime", [
      "start",
      "pma",
      "result-prime",
    ]);
  });

  it("supports back and restart navigation", () => {
    vi.useFakeTimers();
    render(<DecisionTree title="Entity Router" nodes={nodes} />);

    fireEvent.click(screen.getByRole("button", { name: /pt pma/i }));
    expect(screen.getByText("Does the KBLI allow foreign ownership?")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(300);
    });

    fireEvent.click(screen.getByRole("button", { name: /go back/i }));
    expect(screen.getByText("What is the client entity type?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /local pt/i }));

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(screen.getByText("Use local compliance path")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /start over/i })[1]);
    expect(screen.getByText("What is the client entity type?")).toBeInTheDocument();
  });

  it("renders an explicit error when the current node is missing", () => {
    render(
      <DecisionTree
        title="Broken Router"
        nodes={nodes}
        startNodeId="missing-node"
      />,
    );

    expect(screen.getByText("Error: Node not found (ID: missing-node)")).toBeInTheDocument();
  });
});

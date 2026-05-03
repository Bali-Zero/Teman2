import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./tabs";

describe("Tabs", () => {
  it("renders with the default tab active", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>,
    );

    expect(screen.getByText("Content 1")).toBeInTheDocument();
    expect(screen.queryByText("Content 2")).not.toBeInTheDocument();
  });

  it("switches tabs when a trigger is clicked", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>,
    );

    // Click on Tab 2
    fireEvent.click(screen.getByText("Tab 2"));

    expect(screen.queryByText("Content 1")).not.toBeInTheDocument();
    expect(screen.getByText("Content 2")).toBeInTheDocument();
  });

  it("calls onValueChange callback when controlled", () => {
    const onChange = vi.fn();
    render(
      <Tabs defaultValue="tab1" value="tab1" onValueChange={onChange}>
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>,
    );

    fireEvent.click(screen.getByText("Tab 2"));
    expect(onChange).toHaveBeenCalledWith("tab2");
  });

  it("sets data-state attribute on triggers", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
      </Tabs>,
    );

    expect(screen.getByText("Tab 1")).toHaveAttribute(
      "data-state",
      "active",
    );
    expect(screen.getByText("Tab 2")).toHaveAttribute(
      "data-state",
      "inactive",
    );
  });
});

describe("TabsTrigger", () => {
  it("throws when used outside Tabs", () => {
    expect(() =>
      render(<TabsTrigger value="test">Test</TabsTrigger>),
    ).toThrow("TabsTrigger must be used within Tabs");
  });
});

describe("TabsContent", () => {
  it("throws when used outside Tabs", () => {
    expect(() =>
      render(<TabsContent value="test">Content</TabsContent>),
    ).toThrow("TabsContent must be used within Tabs");
  });
});

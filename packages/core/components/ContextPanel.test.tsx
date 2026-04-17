import { describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { ContextPanel } from "./ContextPanel";

describe("ContextPanel", () => {
  it("lazy-renders active tab only", () => {
    const renderInfo = () => <div>INFO_BODY</div>;
    const renderMatter = () => <div>MATTER_BODY</div>;
    const { queryByText, getByRole, getByText } = render(
      <ContextPanel
        open
        tabs={[
          { id: "info", label: "Info", render: renderInfo },
          { id: "matter", label: "Matter", render: renderMatter },
        ]}
      />,
    );
    expect(getByText("INFO_BODY")).toBeTruthy();
    expect(queryByText("MATTER_BODY")).toBeNull();
    fireEvent.click(getByRole("tab", { name: /matter/i }));
    expect(getByText("MATTER_BODY")).toBeTruthy();
  });
});

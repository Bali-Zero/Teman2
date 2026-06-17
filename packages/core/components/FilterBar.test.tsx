import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { FilterBar, FilterSelect } from "./FilterBar";

describe("FilterBar", () => {
  it("renders heading, children and Clear-all when filters are active", () => {
    const onClearAll = vi.fn();
    const { getByText, getByRole } = render(
      <FilterBar activeCount={2} onClearAll={onClearAll}>
        <div>field</div>
      </FilterBar>,
    );
    expect(getByText("Filters")).toBeTruthy();
    expect(getByText("field")).toBeTruthy();
    fireEvent.click(getByRole("button", { name: /Clear all/ }));
    expect(onClearAll).toHaveBeenCalledOnce();
  });

  it("hides Clear-all when no filters are active", () => {
    const { queryByRole } = render(
      <FilterBar activeCount={0} onClearAll={() => undefined}>
        <div />
      </FilterBar>,
    );
    expect(queryByRole("button", { name: /Clear all/ })).toBeNull();
  });
});

describe("FilterSelect", () => {
  it("wires label to select and emits string values on change", () => {
    const onChange = vi.fn();
    const { getByLabelText } = render(
      <FilterSelect
        id="status-filter"
        label="Status"
        value=""
        onChange={onChange}
      >
        <option value="">All statuses</option>
        <option value="active">Active</option>
      </FilterSelect>,
    );
    const select = getByLabelText("Status") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "active" } });
    expect(onChange).toHaveBeenCalledWith("active");
  });

  it("renders labelExtra beside the label when provided", () => {
    const { getByRole } = render(
      <FilterSelect
        label="Assigned To"
        labelExtra={<button>My Clients</button>}
        value=""
        onChange={() => undefined}
      >
        <option value="">All</option>
      </FilterSelect>,
    );
    expect(getByRole("button", { name: "My Clients" })).toBeTruthy();
  });
});

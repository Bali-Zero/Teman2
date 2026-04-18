import * as React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TestimonialCarousel, type Testimonial } from "./TestimonialCarousel";

const samples: Testimonial[] = [
  { quote: "First quote", author: "Alice", rating: 5 },
  { quote: "Second quote", author: "Bob" },
  { quote: "Third quote", author: "Carol" },
];

describe("TestimonialCarousel", () => {
  it("renders the first testimonial initially", () => {
    render(<TestimonialCarousel testimonials={samples} autoPlayMs={0} />);
    expect(screen.getByText(/first quote/i)).toBeInTheDocument();
  });

  it("advances when the Next button is pressed", () => {
    render(<TestimonialCarousel testimonials={samples} autoPlayMs={0} />);
    fireEvent.click(screen.getByRole("button", { name: /next testimonial/i }));
    expect(screen.getByText(/second quote/i)).toBeInTheDocument();
  });

  it("wraps around when pressing Previous from the first slide", () => {
    render(<TestimonialCarousel testimonials={samples} autoPlayMs={0} />);
    fireEvent.click(screen.getByRole("button", { name: /previous testimonial/i }));
    expect(screen.getByText(/third quote/i)).toBeInTheDocument();
  });

  it("supports keyboard navigation via arrow keys", () => {
    render(<TestimonialCarousel testimonials={samples} autoPlayMs={0} />);
    const region = screen.getByRole("region", { hidden: true }) ||
      screen.getByLabelText(/client testimonials/i);
    fireEvent.keyDown(region, { key: "ArrowRight" });
    expect(screen.getByText(/second quote/i)).toBeInTheDocument();
  });

  it("renders nothing when given an empty list", () => {
    const { container } = render(
      <TestimonialCarousel testimonials={[]} autoPlayMs={0} />,
    );
    expect(container.firstChild).toBeNull();
  });
});

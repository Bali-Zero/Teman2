import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { UserAvatar } from "./UserAvatar";

describe("UserAvatar", () => {
  it("renders standard fallback initials from the user name when userAvatar is not provided", () => {
    render(<UserAvatar userName="John Doe" userAvatar={null} />);
    expect(screen.getByText("JO")).toBeInTheDocument();
  });

  it("renders generic fallback 'U' when userName is empty and userAvatar is not provided", () => {
    render(<UserAvatar userName="" userAvatar={null} />);
    expect(screen.getByText("U")).toBeInTheDocument();
  });

  it("renders the user avatar image with dynamic descriptive alt text when provided", () => {
    render(
      <UserAvatar
        userName="John Doe"
        userAvatar="data:image/png;base64,test"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("alt", "Avatar for John Doe");
  });

  it("renders the user avatar image with generic alt text when userName is empty", () => {
    render(<UserAvatar userName="" userAvatar="data:image/png;base64,test" />);
    const img = screen.getByRole("img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("alt", "User avatar");
  });

  it("applies the large size classes and a custom className", () => {
    const { container } = render(
      <UserAvatar
        userName="Zantara"
        userAvatar={null}
        size="lg"
        className="custom-class"
      />,
    );

    expect(container.firstChild).toHaveClass("w-12", "h-12", "custom-class");
  });
});

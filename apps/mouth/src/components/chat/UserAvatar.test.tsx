import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { UserAvatar } from "./UserAvatar";

describe("UserAvatar", () => {
  it("renders with a custom dynamic alt text matching the userName when an avatar image is provided", () => {
    render(
      <UserAvatar
        userName="Zantara"
        userAvatar="https://example.com/avatar.png"
      />
    );
    const img = screen.getByRole("img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("alt", "Avatar for Zantara");
  });

  it("renders with default fallback alt text when no userName is provided but an avatar image exists", () => {
    render(
      <UserAvatar
        userName=""
        userAvatar="https://example.com/avatar.png"
      />
    );
    const img = screen.getByRole("img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("alt", "User avatar");
  });

  it("renders fallback initials when userAvatar is not provided", () => {
    render(<UserAvatar userName="Zantara" userAvatar={null} />);
    expect(screen.getByText("ZA")).toBeInTheDocument();
  });

  it("renders fallback 'U' when userAvatar is null and userName is empty", () => {
    render(<UserAvatar userName="" userAvatar={null} />);
    expect(screen.getByText("U")).toBeInTheDocument();
  });

  it("applies dynamic classes based on size prop and merges custom className", () => {
    const { container } = render(
      <UserAvatar userName="Zantara" userAvatar={null} size="lg" className="custom-class" />
    );
    const div = container.firstChild as HTMLElement;
    expect(div).toHaveClass("w-12", "h-12", "custom-class");
  });
});

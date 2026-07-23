import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { UserAvatar } from "./UserAvatar";

// Mock next/image to render standard HTML img tag for testing
vi.mock("next/image", () => ({
  __esModule: true,
  default: (props: any) => {
    // eslint-disable-next-line @next/next/no-img-element
    return <img {...props} />;
  },
}));

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
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ZantaraPortalCard } from "../ZantaraPortalCard";

describe("ZantaraPortalCard", () => {
  it("keeps the working chat link without a duplicate Zantara mark", () => {
    render(<ZantaraPortalCard />);

    expect(screen.getByRole("link", { name: /Zantara AI/i })).toHaveAttribute(
      "href",
      "https://zantara.balizero.com/chat",
    );
    expect(screen.queryByAltText("Zantara")).not.toBeInTheDocument();
  });
});

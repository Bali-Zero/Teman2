import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ArticleEngagement,
  FloatingEngagementBar,
} from "./ArticleEngagement";

const articleProps = {
  articleId: "article-1",
  articleTitle: "Bali tax update",
  articleUrl: "https://example.test/article",
};

describe("ArticleEngagement", () => {
  beforeEach(() => {
    vi.useRealTimers();
    localStorage.clear();
    vi.spyOn(window, "open").mockImplementation(() => null);
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
    });
  });

  it("loads liked state, toggles likes, and persists localStorage", () => {
    localStorage.setItem("likedArticles", JSON.stringify({ "article-1": true }));

    render(<ArticleEngagement {...articleProps} initialLikes={5} />);

    const likeButton = screen.getByRole("button", { name: "5" });
    expect(likeButton).toHaveClass("text-red-400");

    fireEvent.click(likeButton);

    expect(screen.getByRole("button", { name: "4" })).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("likedArticles") ?? "{}")).toEqual(
      {},
    );
  });

  it("opens share menu, shares to a social target, and closes it", () => {
    render(<ArticleEngagement {...articleProps} />);

    fireEvent.click(screen.getByRole("button", { name: /share/i }));
    fireEvent.click(screen.getByRole("button", { name: /linkedIn/i }));

    expect(window.open).toHaveBeenCalledWith(
      "https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fexample.test%2Farticle",
      "_blank",
    );
  });

  it("copies link from the share menu and shows copied state", async () => {
    render(<ArticleEngagement {...articleProps} />);

    fireEvent.click(screen.getByRole("button", { name: /share/i }));
    fireEvent.click(screen.getByRole("button", { name: /copy link/i }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "https://example.test/article",
      );
    });
    expect(screen.getByText("Copied!")).toBeInTheDocument();
  });

  it("adds a trimmed comment and toggles comment like count", async () => {
    render(<ArticleEngagement {...articleProps} />);

    fireEvent.click(screen.getAllByRole("button", { name: "0" })[1]);
    fireEvent.change(screen.getByLabelText("Your name"), {
      target: { value: "  Made  " },
    });
    fireEvent.focus(screen.getByPlaceholderText("Add a comment..."));
    fireEvent.change(screen.getByPlaceholderText("Add a comment..."), {
      target: { value: "  Useful update.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Post Comment" }));

    await waitFor(() => {
      expect(screen.getByText("Useful update.")).toBeInTheDocument();
    });

    const zeroButtons = screen.getAllByRole("button", { name: "0" });
    const commentLike = zeroButtons[zeroButtons.length - 1];
    expect(commentLike).toBeDefined();
    fireEvent.click(commentLike as HTMLElement);

    expect(commentLike).toHaveClass("text-red-400");
  });
});

describe("FloatingEngagementBar", () => {
  it("dispatches like, comment, and share actions", () => {
    const onLike = vi.fn();
    const onCommentClick = vi.fn();
    const onShare = vi.fn();

    render(
      <FloatingEngagementBar
        articleId="article-1"
        articleTitle="Bali tax update"
        likes={7}
        commentCount={3}
        isLiked={false}
        onLike={onLike}
        onCommentClick={onCommentClick}
        onShare={onShare}
      />,
    );

    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 401,
    });
    fireEvent.scroll(window);

    fireEvent.click(screen.getByRole("button", { name: "7" }));
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    fireEvent.click(screen.getAllByRole("button")[2]);

    expect(onLike).toHaveBeenCalledTimes(1);
    expect(onCommentClick).toHaveBeenCalledTimes(1);
    expect(onShare).toHaveBeenCalledTimes(1);
  });
});

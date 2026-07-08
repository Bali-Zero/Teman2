// Server-side (RSC) MDX renderer.
//
// WHY THIS EXISTS (React-19 fix): next-mdx-remote@6's *client* <MDXRemote>
// (imported from "next-mdx-remote") is hook-based and crashes during SSR under
// React 19 / Next 16 with `TypeError: Cannot read properties of null (reading
// 'useState')` — React's hook dispatcher is null while the serialized MDX
// module re-enters the runtime on the server. That uncaught throw unwinds the
// whole article subtree, so even the page chrome (.rumah-putih wrapper, title,
// byline) is dropped from the SSR HTML and the page renders as a broken shell.
//
// next-mdx-remote@6 ships a React-Server-Component entry ("next-mdx-remote/rsc")
// whose compileMDX compiles + renders MDX on the server with NO client hooks, so
// it works under React 19. We compile the body here (server-side) and hand the
// resulting ReactNode down to the "use client" ArticleClient as a prop — React
// serializes a server-rendered element across the client boundary, and the
// interactive MDX components (which are themselves "use client") hydrate
// normally.
//
// NOTE: deliberately NO "use client" directive — this file MUST stay a server
// component so compileMDX runs on the server.
import type { ReactNode } from "react";
import { compileMDX } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import { mdxComponents } from "./MDXContent";

/**
 * Compile and render an MDX article body on the server (React-19-safe).
 *
 * Returns the rendered ReactNode. Throws if compilation fails — the caller
 * (the article page) awaits this inside a try/catch so a malformed/oversized
 * MDX body degrades to the client-fetch fallback instead of crashing the page.
 *
 * IMPORTANT: this is an awaited function, NOT bare JSX. `compileMDX` does the
 * actual render work eagerly here, so a throw is caught at the call site —
 * unlike `<Component/>` JSX, whose render is deferred past any surrounding
 * try/catch.
 */
export async function renderMDXBody(source: string): Promise<ReactNode> {
  const { content } = await compileMDX({
    source,
    components: mdxComponents,
    options: {
      mdxOptions: {
        remarkPlugins: [remarkGfm],
        development: false,
      },
    },
  });

  return (
    <div
      className="mdx-content"
      style={{ fontSize: "1.3rem", lineHeight: "1.8" }}
    >
      {content}
    </div>
  );
}

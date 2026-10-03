import { I18nProvider } from "@/i18n";
import { R19Presentation } from "@/components/r19/R19Presentation";
import { NotFoundBody } from "@/components/r19/NotFoundBody";
import { BlogNav } from "@/app/(blog)/_components/BlogNav";
import { Footer } from "@/app/v2/_components/Footer";

// Root-level 404: matched for any path that isn't claimed by ANY route (e.g.
// three-plus unknown segments) — `(blog)/not-found.tsx` handles the ones
// `[category]`/`[category]/[slug]` match instead. `force` on R19Presentation
// puts this on the same paper-and-copper design regardless of the pathname,
// since an arbitrary unmatched path never satisfies `routePolicy`'s allow-list.
export default function NotFound() {
  return (
    <I18nProvider>
      <R19Presentation force>
        <div
          className="min-h-screen flex flex-col"
          style={{
            background: "var(--surface-base)",
            color: "var(--text-primary)",
          }}
        >
          <BlogNav />
          <main
            className="flex-1"
            style={{ paddingTop: "var(--public-header-height, 56px)" }}
          >
            <NotFoundBody />
          </main>
          <Footer />
        </div>
      </R19Presentation>
    </I18nProvider>
  );
}

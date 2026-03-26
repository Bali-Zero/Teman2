"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { CHAPTERS, type BookTranslations } from "./book-data";
import { BookNav } from "./BookNav";

interface BookShellContextType {
  onVisible: (id: string) => void;
}

const BookShellContext = createContext<BookShellContextType>({
  onVisible: () => {},
});

export function useBookShell() {
  return useContext(BookShellContext);
}

interface BookShellProps {
  initialChapter?: string;
  translations?: BookTranslations;
  children: React.ReactNode;
}

export function BookShell({
  initialChapter,
  translations,
  children,
}: BookShellProps) {
  const [activeChapter, setActiveChapter] = useState(
    initialChapter ?? CHAPTERS[0].id,
  );

  useEffect(() => {
    if (!initialChapter) return;
    const el = document.getElementById(initialChapter);
    if (el) el.scrollIntoView({ behavior: "instant", block: "start" });
  }, [initialChapter]);

  const handleChapterVisible = useCallback((id: string) => {
    setActiveChapter(id);
    window.history.replaceState(null, "", `/book/${id}`);
    const chapter = CHAPTERS.find((c) => c.id === id);
    if (chapter) document.title = `${chapter.title} — Bali Zero`;
  }, []);

  const handleNavigate = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className="relative">
      <BookNav
        activeChapter={activeChapter}
        onNavigate={handleNavigate}
        chapterNames={translations?.chapters}
      />
      <BookShellContext.Provider value={{ onVisible: handleChapterVisible }}>
        <main className="pb-20 md:pb-0">{children}</main>
      </BookShellContext.Provider>
    </div>
  );
}

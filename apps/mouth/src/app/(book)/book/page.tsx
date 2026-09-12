import { BookPage } from "./BookPage";
import { bookTeamMembers } from "@/components/book/book-team";

export default function BookRootPage() {
  return <BookPage teamMembers={bookTeamMembers()} />;
}

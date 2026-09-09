import type { EditorialFeed } from "../../lib/editorial-feed";

const messages: Record<EditorialFeed["status"], string> = {
  ready: "",
  empty: "No stories have been published in this edition yet.",
  withdrawn: "Stories in this edition are no longer available.",
  unpublished: "The next edition is not published yet.",
  unavailable: "The Journal is temporarily unavailable. Please try again later.",
  malformed: "We could not load this edition reliably. Please try again later.",
};

export function FeedNotice({ status, fixture = false }: { status: EditorialFeed["status"]; fixture?: boolean }) {
  return <>
    {fixture ? <p className="editorial-preview-note">Editorial preview — sample stories and illustration. Original articles and source links are not connected.</p> : null}
    {status !== "ready" ? <p className="editorial-feed-notice" role="status">{messages[status]}</p> : null}
  </>;
}

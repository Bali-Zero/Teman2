// Server boundary for the internal team directory.
//
// The page is "use client" (filters, local state), so its module constants ship to
// the browser. The photo table used to live there and put staff names and portrait
// paths in this route's public chunk — an asset served with no session even though
// the page requires one. It is derived from the roster here instead.
import { teamPhotoMap } from "@/lib/workspace/roster-directory";
import TeamManagementClient from "./TeamManagementClient";

export default function TeamPage() {
  return <TeamManagementClient teamPhotos={teamPhotoMap()} />;
}

import json
import re


# --- Paste relevant code from reasoning.py ---
def detect_team_query(query: str) -> tuple[bool, str, str]:
    if not isinstance(query, str):
        return False, "", ""
    q = query.strip()
    if not q:
        return False, "", ""
    ql = q.lower()

    # 1) List-all
    list_all_markers = (
        "list all team",
        "list team",
        "team members",
        "membri del team",
        "lista team",
        "elenco team",
        "tutti i membri",
        "quanti dipendenti",
        "vostri dipendenti",
        "dipendenti del team",
        "tutto lo staff",
        "vostro staff",
        "il vostro personale",
    )
    if any(marker in ql for marker in list_all_markers):
        return True, "list_all", ""

    # 2) Email
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", q)
    if email_match:
        return True, "search_by_email", email_match.group(0)

    # 3) Role/title
    team_context_markers = (
        "chi si occupa",
        "chi gestisce",
        "chi segue",
        "chi è il",
        "chi è la",
        "who handles",
        "who manages",
        "who is the",
        "who is your",
        "your team",
        "nel team",
        "del team",
        "in the team",
        "team member",
        "staff member",
        "il vostro",
        "la vostra",
        "avete qualcuno",
        "c'è qualcuno",
        "esperto di",
        "specialist",
        "manager",
        "responsabile",
    )
    has_team_context = any(marker in ql for marker in team_context_markers)

    if has_team_context:
        role_map = {
            "ceo": ("ceo", "chief executive", "amministratore delegato", "a.d.", "ad "),
            "founder": (
                "founder",
                "cofounder",
                "co-founder",
                "fondatore",
                "fondatrice",
            ),
            "tax": ("tax", "tasse", "fiscale", "fiscal", "pajak"),
            "visa": ("visa", "visti", "immigrazione", "immigration"),
            "setup": ("setup", "set up", "onboarding"),
            "legal": ("legal", "legale", "law", "avvocato"),
            "property": ("property", "immobiliare", "real estate"),
            "marketing": ("marketing", "social", "content"),
            "support": ("support", "assistenza", "customer care"),
        }
        for role, keywords in role_map.items():
            if any(k in ql for k in keywords):
                return True, "search_by_role", role

    # 4) Name (simplified)
    name_patterns = (r"\bchi\s*[eè]['']?\s*(?P<term>[^?.,!;:\n]{1,64})",)
    # ... logic skipped as 3 matches priority

    return False, "", ""


# --- Paste relevant code from tools.py (mocked) ---
class TeamKnowledgeTool:
    def execute(self, query_type="list_all", search_term="", team_data=None):
        search_term = search_term.lower().strip() if search_term else ""
        if query_type == "list_all":
            return [m["name"] for m in team_data]

        matches = [m for m in team_data if search_term in json.dumps(m).lower()]
        return matches


# --- Test ---
query = "Chi è il CEO di Nuzantara?"
print(f"Query: {query}")
is_team, q_type, term = detect_team_query(query)
print(f"Detection: is_team={is_team}, type={q_type}, term={term}")

# Load actual data
try:
    with open("apps/backend-rag/backend/data/team_members.json") as f:
        data = json.load(f)
    print(f"Data loaded: {len(data)} records")

    tool = TeamKnowledgeTool()
    results = tool.execute(query_type=q_type, search_term=term, team_data=data)
    print(f"Tool Matches: {len(results)}")
    if results:
        print(f"Match 1: {results[0].get('name')} - {results[0].get('role')}")
except Exception as e:
    print(f"Error loading data: {e}")

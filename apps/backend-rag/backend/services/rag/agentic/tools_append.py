
class TimeSheetTool(BaseTool):
    """Tool for team timesheet management (clock-in, clock-out, status)"""

    def __init__(self):
        self._team_data = None

    @property
    def name(self) -> str:
        return "timesheet"

    @property
    def description(self) -> str:
        return (
            "Manage work timesheet. Use this to clock in, clock out, or check work status. "
            "REQUIRED: User email address."
            "Actions: clock_in, clock_out, status"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["clock_in", "clock_out", "status"],
                    "description": "Action to perform",
                },
                "email": {
                    "type": "string",
                    "description": "User email address (required)",
                },
            },
            "required": ["action", "email"],
        }
    
    def _get_user_id_by_email(self, email: str) -> str | None:
        try:
           from pathlib import Path
           # Try relative to this file
           path = Path(__file__).parent.parent.parent.parent / "data" / "team_members.json"
           if not path.exists():
               path = Path("/app/backend/data/team_members.json")
           
           if path.exists():
               with open(path) as f:
                   data = json.load(f)
                   for m in data:
                       if m.get("email", "").lower() == email.lower():
                           return m.get("id")
        except Exception:
            pass
        return None

    async def execute(self, action: str, email: str, **kwargs) -> str:
        try:
            from services.analytics.team_timesheet_service import get_timesheet_service
            
            service = get_timesheet_service()
            if not service:
                return json.dumps({"error": "Timesheet service unavailable"})

            user_id = self._get_user_id_by_email(email)
            if not user_id:
                return json.dumps({"error": f"User ID not found for email {email}"})

            if action == "clock_in":
                res = await service.clock_in(user_id, email, metadata={"source": "agent"})
                return json.dumps(res)
            elif action == "clock_out":
                res = await service.clock_out(user_id, email, metadata={"source": "agent"})
                return json.dumps(res)
            elif action == "status":
                res = await service.get_my_status(user_id)
                return json.dumps(res)
            else:
                 return json.dumps({"error": f"Unknown action {action}"})

        except Exception as e:
            return json.dumps({"error": str(e)})

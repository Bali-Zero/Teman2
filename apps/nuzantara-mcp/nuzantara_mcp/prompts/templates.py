"""Expanded Prompt Templates - 10 structured prompts for common scenarios."""


def register(mcp):
    # --- Original 3 prompts (migrated) ---

    @mcp.prompt()
    def immigration_check(visa_type: str, nationality: str) -> str:
        """Template for immigration eligibility questions."""
        return (
            f"I need information about {visa_type} visa for {nationality} nationals in Indonesia. "
            "Please provide: eligibility requirements, application process, "
            "required documents, processing time and costs, common issues."
        )

    @mcp.prompt()
    def business_setup(business_type: str, investor_type: str = "foreign") -> str:
        """Template for business setup guidance in Indonesia."""
        return (
            f"I want to establish a {business_type} business in Indonesia as a {investor_type} investor. "
            "Guide me through: recommended company structure (PT, PT PMA), "
            "required KBLI codes, licenses and permits, capital requirements, step-by-step process."
        )

    @mcp.prompt()
    def kbli_comparison(code1: str, code2: str) -> str:
        """Template to compare two KBLI codes."""
        return (
            f"Compare KBLI {code1} and KBLI {code2}: "
            "What does each cover? What are the differences in PMA status, "
            "risk category, and licensing requirements? "
            "When should I choose one over the other?"
        )

    # --- New prompts ---

    @mcp.prompt()
    def client_onboarding_brief(
        client_name: str,
        nationality: str,
        business_type: str,
    ) -> str:
        """Generate a structured onboarding brief for a new client."""
        return (
            f"Prepare an onboarding brief for new client: {client_name} ({nationality}), "
            f"business type: {business_type}.\n\n"
            "Include:\n"
            "1. Recommended visa type and timeline\n"
            "2. Required KBLI codes for their business\n"
            "3. Company structure recommendation (PT PMA vs PT Perorangan)\n"
            "4. Required documents checklist\n"
            "5. Estimated costs and timeline\n"
            "6. Potential issues based on nationality\n"
            "7. First 3 action items"
        )

    @mcp.prompt()
    def practice_status_report(practice_type: str, client_name: str) -> str:
        """Generate a client-facing practice status report."""
        return (
            f"Generate a clear, professional status report for {client_name}'s {practice_type} practice.\n\n"
            "Include:\n"
            "1. Current status and progress percentage\n"
            "2. Completed steps with dates\n"
            "3. Current step and what's happening now\n"
            "4. Next steps and estimated timeline\n"
            "5. Documents still needed (if any)\n"
            "6. Any blockers or delays\n"
            "Keep the language simple and reassuring."
        )

    @mcp.prompt()
    def regulatory_impact_assessment(regulation_title: str, source: str = "unknown") -> str:
        """Assess the impact of a regulatory change on foreign investors in Bali."""
        return (
            f"Analyze the impact of this regulatory change: '{regulation_title}' (source: {source})\n\n"
            "Provide:\n"
            "1. Summary of the change in plain language\n"
            "2. Who is affected (which visa types, business types)\n"
            "3. Impact severity (low/medium/high/critical)\n"
            "4. Required actions for affected clients\n"
            "5. Timeline for compliance\n"
            "6. Recommended communication to clients"
        )

    @mcp.prompt()
    def weekly_ops_summary(week_date: str) -> str:
        """Template for weekly operations summary."""
        return (
            f"Generate a concise weekly operations summary for the week of {week_date}.\n\n"
            "Structure:\n"
            "1. Key metrics (clients, practices, revenue)\n"
            "2. Completed milestones\n"
            "3. Active issues and blockers\n"
            "4. Team performance highlights\n"
            "5. Regulatory updates of the week\n"
            "6. Priorities for next week\n"
            "Keep it under 500 words."
        )

    @mcp.prompt()
    def client_renewal_notice(
        client_name: str, document_type: str, expiry_date: str, days_remaining: int
    ) -> str:
        """Generate a personalized renewal notice for a client."""
        return (
            f"Draft a professional and friendly renewal notice for {client_name}.\n"
            f"Their {document_type} expires on {expiry_date} ({days_remaining} days remaining).\n\n"
            "Include:\n"
            "1. Warm greeting\n"
            "2. Clear statement of what's expiring and when\n"
            "3. Required documents for renewal\n"
            "4. Estimated renewal timeline and cost\n"
            "5. Call to action (schedule a call or visit portal)\n"
            "6. Consequence of late renewal\n"
            "Tone: professional but warm, not alarmist."
        )

    @mcp.prompt()
    def team_performance_review(period: str = "monthly") -> str:
        """Template for team performance review analysis."""
        return (
            f"Analyze team performance for the {period} period.\n\n"
            "Cover:\n"
            "1. Practices completed per team member\n"
            "2. Average response times by channel\n"
            "3. Client satisfaction scores\n"
            "4. Workload distribution (is it balanced?)\n"
            "5. Overtime and burnout risk indicators\n"
            "6. Top performer and areas for improvement\n"
            "7. Recommendations for next period"
        )

    @mcp.prompt()
    def competitive_intel_brief(topic: str) -> str:
        """Template for competitive intelligence briefing."""
        return (
            f"Prepare a competitive intelligence brief about: {topic}\n\n"
            "Include:\n"
            "1. Current market landscape in Bali for this service\n"
            "2. Key competitors and their positioning\n"
            "3. Pricing comparison (where available)\n"
            "4. Our competitive advantages\n"
            "5. Gaps and opportunities\n"
            "6. Recommended positioning adjustments"
        )

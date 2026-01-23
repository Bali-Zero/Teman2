from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder


def test_build_system_prompt_injects_email():
    """Verify that the user's email is correctly injected into the system prompt."""
    builder = SystemPromptBuilder()

    # Mock user context
    user_id = "test_user_id"
    user_email = "test@balizero.com"
    context = {
        "profile": {
            "name": "Test User",
            "email": user_email,
            "role": "Team Member",
            "department": "Engineering",
            "notes": "Test notes",
        }
    }

    # Build prompt
    prompt = builder.build_system_prompt(user_id=user_id, context=context, query="Clock in please")

    # Assertions
    assert f"Email: {user_email}" in prompt
    assert "User Name: Test User" in prompt
    assert "Role: Team Member" in prompt


def test_build_system_prompt_fallback_email_from_id():
    """Verify email fallback extraction from user_id if profile is missing email."""
    builder = SystemPromptBuilder()

    user_id = "fallback@balizero.com"
    context = {"entities": {"user_name": "Fallback User"}}

    prompt = builder.build_system_prompt(user_id=user_id, context=context, query="Clock in")

    assert f"Email: {user_id}" in prompt
    assert "User Name: Fallback User" in prompt

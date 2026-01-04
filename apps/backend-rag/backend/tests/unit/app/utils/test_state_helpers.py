"""
Unit tests for state_helpers
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.utils.state_helpers import get_app_state, get_request_state


class TestGetAppState:
    """Tests for get_app_state function"""

    def test_get_existing_attribute(self):
        """Test getting existing attribute"""
        app_state = MagicMock()
        app_state.memory_service = "test_service"

        result = get_app_state(app_state, "memory_service")
        assert result == "test_service"

    def test_get_non_existing_attribute_with_default(self):
        """Test getting non-existing attribute with default"""
        app_state = MagicMock()
        del app_state.memory_service  # Ensure it doesn't exist

        result = get_app_state(app_state, "memory_service", default="default_value")
        assert result == "default_value"

    def test_get_non_existing_attribute_no_default(self):
        """Test getting non-existing attribute without default"""
        app_state = MagicMock()
        del app_state.memory_service

        result = get_app_state(app_state, "memory_service")
        assert result is None

    def test_get_attribute_with_correct_type(self):
        """Test getting attribute with correct type check"""
        app_state = MagicMock()
        app_state.memory_service = "test_service"

        result = get_app_state(app_state, "memory_service", expected_type=str)
        assert result == "test_service"

    def test_get_attribute_with_wrong_type(self):
        """Test getting attribute with wrong type check"""
        app_state = MagicMock()
        app_state.memory_service = "test_service"  # String, not int

        result = get_app_state(app_state, "memory_service", default=None, expected_type=int)
        assert result is None  # Should return default due to type mismatch

    def test_get_attribute_none_value(self):
        """Test getting attribute that is None"""
        app_state = MagicMock()
        app_state.memory_service = None

        result = get_app_state(app_state, "memory_service", default="default")
        assert result == "default"  # Should return default when value is None

    def test_get_attribute_none_value_no_default(self):
        """Test getting attribute that is None without default"""
        app_state = MagicMock()
        app_state.memory_service = None

        result = get_app_state(app_state, "memory_service")
        assert result is None

    def test_get_attribute_with_class_type(self):
        """Test getting attribute with class type check"""

        class TestService:
            pass

        app_state = MagicMock()
        app_state.service = TestService()

        result = get_app_state(app_state, "service", expected_type=TestService)
        assert isinstance(result, TestService)

    def test_get_attribute_with_wrong_class_type(self):
        """Test getting attribute with wrong class type"""

        class TestService:
            pass

        class OtherService:
            pass

        app_state = MagicMock()
        app_state.service = TestService()

        result = get_app_state(app_state, "service", default=None, expected_type=OtherService)
        assert result is None  # Should return default due to type mismatch


class TestGetRequestState:
    """Tests for get_request_state function"""

    def test_get_existing_attribute(self):
        """Test getting existing attribute"""
        request_state = MagicMock()
        request_state.user_id = "user123"

        result = get_request_state(request_state, "user_id")
        assert result == "user123"

    def test_get_non_existing_attribute_with_default(self):
        """Test getting non-existing attribute with default"""
        request_state = MagicMock()
        del request_state.user_id

        result = get_request_state(request_state, "user_id", default="default_user")
        assert result == "default_user"

    def test_get_non_existing_attribute_no_default(self):
        """Test getting non-existing attribute without default"""
        request_state = MagicMock()
        del request_state.user_id

        result = get_request_state(request_state, "user_id")
        assert result is None

    def test_get_attribute_with_correct_type(self):
        """Test getting attribute with correct type check"""
        request_state = MagicMock()
        request_state.user_id = "user123"

        result = get_request_state(request_state, "user_id", expected_type=str)
        assert result == "user123"

    def test_get_attribute_with_wrong_type(self):
        """Test getting attribute with wrong type check"""
        request_state = MagicMock()
        request_state.user_id = "user123"  # String, not int

        result = get_request_state(request_state, "user_id", default=None, expected_type=int)
        assert result is None  # Should return default due to type mismatch

    def test_get_attribute_none_value(self):
        """Test getting attribute that is None"""
        request_state = MagicMock()
        request_state.user_id = None

        result = get_request_state(request_state, "user_id", default="default_user")
        assert result == "default_user"  # Should return default when value is None

    def test_get_attribute_none_value_no_default(self):
        """Test getting attribute that is None without default"""
        request_state = MagicMock()
        request_state.user_id = None

        result = get_request_state(request_state, "user_id")
        assert result is None

    def test_get_attribute_with_dict_like_object(self):
        """Test getting attribute from dict-like object"""

        class DictLike:
            def __init__(self):
                self.data = {"user_id": "user123"}

            def __getattr__(self, name):
                return self.data.get(name)

        request_state = DictLike()
        result = get_request_state(request_state, "user_id")
        assert result == "user123"

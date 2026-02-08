# Docstring Standards

Docstrings are mandatory for:

- FastAPI endpoint handlers
- Public service classes
- Public service methods
- Utility functions that are imported across modules

These docstrings become part of the OpenAPI schema and are required to keep the
documentation complete and accurate.

## Endpoint Docstring Template

```python
@router.post("/example", response_model=ExampleResponse)
async def example_endpoint(payload: ExampleRequest) -> ExampleResponse:
    """
    Short, user-facing summary of the endpoint.

    Optional longer description with:
    - behavior and important side-effects
    - authorization requirements
    - any relevant defaults or assumptions
    """
    ...
```

## Service Docstring Template

```python
class ExampleService:
    """
    Short summary of the service responsibility.

    Detailed description of behavior, dependencies, and usage.

    Attributes:
        repository: Data access layer instance.
        cache: Optional cache dependency.
    """

    async def perform(self, value: str) -> Result:
        """
        Summary of the method behavior.

        Args:
            value: Input parameter.

        Returns:
            Result of the operation.

        Raises:
            ValueError: When value is invalid.
        """
```

## Requirements Checklist

- Every endpoint has a docstring.
- Docstrings are concise, accurate, and user-facing.
- Use `Args`, `Returns`, and `Raises` where relevant.
- Keep docstrings in sync with business logic and response models.

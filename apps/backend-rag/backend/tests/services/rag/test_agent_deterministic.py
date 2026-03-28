import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator


class NPWPValidationSchema(BaseModel):
    """Schema deterministico per il tool Pydantic di estrazione NPWP."""

    npwp_number: str = Field(..., description="15 or 16 digit Indonesian NPWP")
    status: str = Field(..., description="Extracted status of NPWP")

    @field_validator("npwp_number")
    @classmethod
    def validate_npwp(cls, v: str) -> str:
        cleaned = v.replace(".", "").replace("-", "")
        if not cleaned.isdigit():
            raise ValueError("NPWP must contain only numbers.")

        if len(cleaned) not in [15, 16]:
            raise ValueError(f"NPWP must be 15 or 16 digits long. Got {len(cleaned)} digits.")

        return cleaned


class KBLIMatchingSchema(BaseModel):
    """Schema deterministico per il matching di KBLI."""

    code: str = Field(..., description="5 digit KBLI exactly")
    confidence_score: float = Field(..., description="AI confidence score for the match")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 5:
            raise ValueError("KBLI code must be exactly 5 digits.")
        return v

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0.")
        if v < 0.60:
            raise ValueError(
                "Confidence < 0.60 requires manual review or fallback. Discarding deterministic match.",
            )
        return v


@pytest.mark.asyncio
async def test_deterministic_npwp_validation():
    # TEST PASS: Formato valido
    valid_data = {"npwp_number": "01.234.567.8-901.234", "status": "Active"}
    model = NPWPValidationSchema(**valid_data)
    assert model.npwp_number.replace(".", "").replace("-", "") == "012345678901234"
    assert model.status == "Active"

    # TEST FAIL: Stringa non numerica
    invalid_data = {"npwp_number": "01.ABC.567.8-901", "status": "Active"}
    with pytest.raises(ValidationError):
        NPWPValidationSchema(**invalid_data)


@pytest.mark.asyncio
async def test_deterministic_kbli_validation():
    # TEST PASS
    valid_data = {"code": "47911", "confidence_score": 0.85}
    model = KBLIMatchingSchema(**valid_data)
    assert model.code == "47911"
    assert model.confidence_score == 0.85

    # TEST FAIL: Bassa confidenza (Evidence Scoring < 0.60)
    invalid_data = {"code": "47911", "confidence_score": 0.45}
    with pytest.raises(ValidationError):
        KBLIMatchingSchema(**invalid_data)

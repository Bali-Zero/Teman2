"""
Knowledge Base - Visa Types Router
Professional visa cards for Bali Zero

Provides endpoints for:
- Listing all visa types
- Getting individual visa details
- Filtering by category
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies import get_database_pool as get_db_pool

router = APIRouter(prefix="/api/knowledge/visa", tags=["knowledge-visa"])


# =============================================================================
# Pydantic Models
# =============================================================================


class VisaTypeBase(BaseModel):
    """Base visa type model"""

    code: str
    name: str
    category: str
    duration: str | None = None
    extensions: str | None = None
    total_stay: str | None = None
    renewable: bool = False
    processing_time_normal: str | None = None
    processing_time_express: str | None = None
    processing_timeline: dict | None = None
    cost_visa: str | None = None
    cost_extension: str | None = None
    cost_details: dict | None = None
    requirements: list[str] = []
    restrictions: list[str] = []
    allowed_activities: list[str] = []
    benefits: list[str] = []
    process_steps: list[str] = []
    tips: list[str] = []
    foreign_eligible: bool = True
    metadata: dict | None = None


class VisaTypeResponse(VisaTypeBase):
    """Response model with ID and timestamps"""

    id: int
    last_updated: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class VisaTypeListResponse(BaseModel):
    """List response with pagination info"""

    items: list[VisaTypeResponse]
    total: int
    categories: list[str]


class VisaTypeCreate(VisaTypeBase):
    """Create model"""

    pass


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=VisaTypeListResponse)
async def list_visa_types(category: str | None = None, pool=Depends(get_db_pool)):
    """
    List all visa types, optionally filtered by category.

    Categories: KITAS, KITAP, Tourist, Business, Social
    """
    async with pool.acquire() as conn:
        # Build query
        if category:
            query = """
                SELECT * FROM visa_types
                WHERE LOWER(category) = LOWER($1)
                ORDER BY
                    CASE category
                        WHEN 'KITAS' THEN 1
                        WHEN 'KITAP' THEN 2
                        WHEN 'Tourist' THEN 3
                        WHEN 'Business' THEN 4
                        ELSE 5
                    END,
                    name
            """
            rows = await conn.fetch(query, category)
        else:
            query = """
                SELECT * FROM visa_types
                ORDER BY
                    CASE category
                        WHEN 'KITAS' THEN 1
                        WHEN 'KITAP' THEN 2
                        WHEN 'Tourist' THEN 3
                        WHEN 'Business' THEN 4
                        ELSE 5
                    END,
                    name
            """
            rows = await conn.fetch(query)

        # Get unique categories
        categories_query = "SELECT DISTINCT category FROM visa_types ORDER BY category"
        cat_rows = await conn.fetch(categories_query)
        categories = [r["category"] for r in cat_rows if r["category"]]

        items = [
            VisaTypeResponse(
                id=row["id"],
                code=row["code"],
                name=row["name"],
                category=row["category"] or "Other",
                duration=row["duration"],
                extensions=row["extensions"],
                total_stay=row["total_stay"],
                renewable=row["renewable"] or False,
                processing_time_normal=row["processing_time_normal"],
                processing_time_express=row["processing_time_express"],
                processing_timeline=row["processing_timeline"],
                cost_visa=row["cost_visa"],
                cost_extension=row["cost_extension"],
                cost_details=row["cost_details"],
                requirements=row["requirements"] or [],
                restrictions=row["restrictions"] or [],
                allowed_activities=row["allowed_activities"] or [],
                benefits=row["benefits"] or [],
                process_steps=row["process_steps"] or [],
                tips=row["tips"] or [],
                foreign_eligible=row["foreign_eligible"]
                if row["foreign_eligible"] is not None
                else True,
                metadata=row["metadata"],
                last_updated=row["last_updated"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

        return VisaTypeListResponse(items=items, total=len(items), categories=categories)


@router.get("/{visa_id}", response_model=VisaTypeResponse)
async def get_visa_type(visa_id: int, pool=Depends(get_db_pool)):
    """Get a specific visa type by ID"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM visa_types WHERE id = $1", visa_id)

        if not row:
            raise HTTPException(status_code=404, detail="Visa type not found")

        return VisaTypeResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            category=row["category"] or "Other",
            duration=row["duration"],
            extensions=row["extensions"],
            total_stay=row["total_stay"],
            renewable=row["renewable"] or False,
            processing_time_normal=row["processing_time_normal"],
            processing_time_express=row["processing_time_express"],
            processing_timeline=row["processing_timeline"],
            cost_visa=row["cost_visa"],
            cost_extension=row["cost_extension"],
            cost_details=row["cost_details"],
            requirements=row["requirements"] or [],
            restrictions=row["restrictions"] or [],
            allowed_activities=row["allowed_activities"] or [],
            benefits=row["benefits"] or [],
            process_steps=row["process_steps"] or [],
            tips=row["tips"] or [],
            foreign_eligible=row["foreign_eligible"]
            if row["foreign_eligible"] is not None
            else True,
            metadata=row["metadata"],
            last_updated=row["last_updated"],
            created_at=row["created_at"],
        )


@router.get("/code/{code}", response_model=VisaTypeResponse)
async def get_visa_by_code(code: str, pool=Depends(get_db_pool)):
    """Get a specific visa type by code (e.g., 'C316', 'KITAS-INVESTOR')"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM visa_types WHERE UPPER(code) = UPPER($1)", code)

        if not row:
            raise HTTPException(status_code=404, detail=f"Visa type with code '{code}' not found")

        return VisaTypeResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            category=row["category"] or "Other",
            duration=row["duration"],
            extensions=row["extensions"],
            total_stay=row["total_stay"],
            renewable=row["renewable"] or False,
            processing_time_normal=row["processing_time_normal"],
            processing_time_express=row["processing_time_express"],
            processing_timeline=row["processing_timeline"],
            cost_visa=row["cost_visa"],
            cost_extension=row["cost_extension"],
            cost_details=row["cost_details"],
            requirements=row["requirements"] or [],
            restrictions=row["restrictions"] or [],
            allowed_activities=row["allowed_activities"] or [],
            benefits=row["benefits"] or [],
            process_steps=row["process_steps"] or [],
            tips=row["tips"] or [],
            foreign_eligible=row["foreign_eligible"]
            if row["foreign_eligible"] is not None
            else True,
            metadata=row["metadata"],
            last_updated=row["last_updated"],
            created_at=row["created_at"],
        )


class VisaTypeUpdate(BaseModel):
    """Update model - all fields optional"""

    name: str | None = None
    category: str | None = None
    duration: str | None = None
    extensions: str | None = None
    total_stay: str | None = None
    renewable: bool | None = None
    processing_time_normal: str | None = None
    processing_time_express: str | None = None
    processing_timeline: dict | None = None
    cost_visa: str | None = None
    cost_extension: str | None = None
    cost_details: dict | None = None
    requirements: list[str] | None = None
    restrictions: list[str] | None = None
    allowed_activities: list[str] | None = None
    benefits: list[str] | None = None
    process_steps: list[str] | None = None
    tips: list[str] | None = None
    foreign_eligible: bool | None = None
    metadata: dict | None = None


@router.put("/{visa_id}", response_model=VisaTypeResponse)
async def update_visa_type(visa_id: int, visa: VisaTypeUpdate, pool=Depends(get_db_pool)):
    """Update a visa type by ID"""
    async with pool.acquire() as conn:
        # Check if exists
        existing = await conn.fetchrow("SELECT * FROM visa_types WHERE id = $1", visa_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Visa type not found")

        # Build dynamic update
        updates = []
        values = []
        param_idx = 1

        for field, value in visa.model_dump(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                values.append(value)
                param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append("last_updated = NOW()")
        values.append(visa_id)

        query = f"""
            UPDATE visa_types
            SET {", ".join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(query, *values)

        return VisaTypeResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            category=row["category"] or "Other",
            duration=row["duration"],
            extensions=row["extensions"],
            total_stay=row["total_stay"],
            renewable=row["renewable"] or False,
            processing_time_normal=row["processing_time_normal"],
            processing_time_express=row["processing_time_express"],
            processing_timeline=row["processing_timeline"],
            cost_visa=row["cost_visa"],
            cost_extension=row["cost_extension"],
            cost_details=row["cost_details"],
            requirements=row["requirements"] or [],
            restrictions=row["restrictions"] or [],
            allowed_activities=row["allowed_activities"] or [],
            benefits=row["benefits"] or [],
            process_steps=row["process_steps"] or [],
            tips=row["tips"] or [],
            foreign_eligible=row["foreign_eligible"]
            if row["foreign_eligible"] is not None
            else True,
            metadata=row["metadata"],
            last_updated=row["last_updated"],
            created_at=row["created_at"],
        )


@router.post("/", response_model=VisaTypeResponse)
async def create_visa_type(visa: VisaTypeCreate, pool=Depends(get_db_pool)):
    """Create a new visa type (admin only)"""
    async with pool.acquire() as conn:
        # Check if code already exists
        existing = await conn.fetchval(
            "SELECT id FROM visa_types WHERE UPPER(code) = UPPER($1)", visa.code
        )
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Visa type with code '{visa.code}' already exists"
            )

        row = await conn.fetchrow(
            """
            INSERT INTO visa_types (
                code, name, category, duration, extensions, total_stay, renewable,
                processing_time_normal, processing_time_express, processing_timeline,
                cost_visa, cost_extension, cost_details,
                requirements, restrictions, allowed_activities, benefits, process_steps, tips,
                foreign_eligible, metadata, created_at, last_updated
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17, $18, $19, $20, $21, NOW(), NOW()
            )
            RETURNING *
            """,
            visa.code,
            visa.name,
            visa.category,
            visa.duration,
            visa.extensions,
            visa.total_stay,
            visa.renewable,
            visa.processing_time_normal,
            visa.processing_time_express,
            visa.processing_timeline,
            visa.cost_visa,
            visa.cost_extension,
            visa.cost_details,
            visa.requirements,
            visa.restrictions,
            visa.allowed_activities,
            visa.benefits,
            visa.process_steps,
            visa.tips,
            visa.foreign_eligible,
            visa.metadata,
        )

        return VisaTypeResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            category=row["category"] or "Other",
            duration=row["duration"],
            extensions=row["extensions"],
            total_stay=row["total_stay"],
            renewable=row["renewable"] or False,
            processing_time_normal=row["processing_time_normal"],
            processing_time_express=row["processing_time_express"],
            processing_timeline=row["processing_timeline"],
            cost_visa=row["cost_visa"],
            cost_extension=row["cost_extension"],
            cost_details=row["cost_details"],
            requirements=row["requirements"] or [],
            restrictions=row["restrictions"] or [],
            allowed_activities=row["allowed_activities"] or [],
            benefits=row["benefits"] or [],
            process_steps=row["process_steps"] or [],
            tips=row["tips"] or [],
            foreign_eligible=row["foreign_eligible"]
            if row["foreign_eligible"] is not None
            else True,
            metadata=row["metadata"],
            last_updated=row["last_updated"],
            created_at=row["created_at"],
        )

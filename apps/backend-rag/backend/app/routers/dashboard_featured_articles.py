"""
Dashboard Featured Articles Router

Provides featured articles for the dashboard widget.
Currently returns static articles, but can be extended to fetch from database/API.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/featured-articles")
async def get_featured_articles() -> dict:
    """
    Get featured articles for dashboard widget.

    Currently returns static articles from balizero.com.
    Can be extended to fetch from database or external API.
    """
    return {
        "articles": [
            {
                "id": "1",
                "title": "Suwung Landfill Closure: The Waste Crisis Hitting Bali's Tourist Zones",
                "category": "LIFESTYLE",
                "categoryColor": "text-red-400",
                "imageUrl": "/static/news/suwung-landfill.jpg",
                "href": "https://balizero.com/articles/lifestyle/suwung-landfill-crisis",
            },
            {
                "id": "2",
                "title": "Property Alert: Green Zone Crackdown and the End of Easy Villa Permits",
                "category": "PROPERTY",
                "categoryColor": "text-amber-400",
                "imageUrl": "/static/news/property-green-zone.jpg",
                "href": "https://balizero.com/articles/property/property-green-zone-alert",
            },
            {
                "id": "3",
                "title": "Dengue Alert 2026: 636 Cases and Rising — What Expats Need to Know",
                "category": "LIFESTYLE",
                "categoryColor": "text-red-400",
                "imageUrl": "/static/news/dengue-alert.jpg",
                "href": "https://balizero.com/articles/lifestyle/dengue-alert-2026",
            },
            {
                "id": "4",
                "title": "The 40-75% Tax Shock: What Pajak Hiburan Means for Beach Clubs and Nightlife",
                "category": "TAX & LEGAL",
                "categoryColor": "text-cyan-400",
                "imageUrl": "/static/news/pajak-hiburan.jpg",
                "href": "https://balizero.com/articles/tax-legal/pajak-hiburan-tax-shock",
            },
            {
                "id": "5",
                "title": "The Constitutional Clash: Can Bali Legally Demand Your Bank Statements?",
                "category": "IMMIGRATION",
                "categoryColor": "text-blue-400",
                "imageUrl": "/static/news/constitutional-clash-koster.jpg",
                "href": "https://balizero.com/articles/immigration/constitutional-clash-bank-statements",
                "isFeatured": True,
            },
        ],
    }

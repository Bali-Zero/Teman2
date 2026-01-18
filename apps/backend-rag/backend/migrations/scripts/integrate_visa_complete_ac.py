#!/usr/bin/env python3
"""
Complete A-C series visa integration from corrected_EN.txt
Includes all details: purpose, requirements, costs, duration, sponsor info.

Run: fly ssh console -a nuzantara-rag -C "python /app/backend/migrations/integrate_visa_complete_ac.py"
"""

import asyncio
import json
import os

import asyncpg

# Complete visa data from visa_indonesia_corrected_EN.txt
VISA_DATA = {
    # ==================== A SERIES - VISA FREE ====================
    "A1": {
        "name": "A1 - Tourism",
        "category": "Visa Free",
        "duration": "30 days",
        "cost_visa": "FREE",
        "processing_time_normal": "Instant",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Return or onward ticket to another country",
            "Certain nationalities only (visa-free eligible)",
        ],
        "benefits": [
            "Tourism and leisure activities",
            "Visiting family and friends",
            "Attending MICE events (meetings, incentives, conventions, exhibitions)",
            "Transit to another country",
            "No sponsor required",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "extendable": False,
            "convertible": False,
            "sponsor_required": False,
            "work_allowed": False,
            "restrictions": [
                "Cannot be extended",
                "Cannot be converted to other permit types",
                "Prohibited from selling goods/services",
                "Prohibited from receiving wages from Indonesian sources",
                "Not available for stateless persons",
                "Not for temporary/emergency passport holders",
            ],
            "application_methods": [
                "Upon Arrival",
                "Pre-Arrival Electronic (evisa.imigrasi.go.id)",
            ],
        },
    },
    "A4": {
        "name": "A4 - Government Assignment",
        "category": "Visa Free",
        "duration": "30 days",
        "cost_visa": "FREE",
        "processing_time_normal": "Instant",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Return or onward ticket",
            "Official government assignment documentation",
        ],
        "benefits": [
            "Government duties and official assignments",
            "Tourism activities while on assignment",
            "Visiting friends and family",
            "No sponsor required",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "extendable": False,
            "convertible": False,
            "sponsor_required": False,
            "purpose": "Government Assignment",
        },
    },
    "A36": {
        "name": "A36 - Ship and Aircraft Crew",
        "category": "Visa Free",
        "duration": "30 days",
        "cost_visa": "FREE",
        "processing_time_normal": "Instant",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Listed in General Declaration or Crew List",
            "Active crew member (captain, pilot, or crew)",
        ],
        "benefits": [
            "Work duties on transport vehicles",
            "Tourism during shore leave",
            "Shopping and personal activities",
            "No sponsor required",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "extendable": False,
            "convertible": False,
            "crew_type": ["Captain", "Pilot", "Active Crew"],
            "work_allowed": True,
            "work_type": "Transport crew duties only",
        },
    },
    "A37": {
        "name": "A37 - Ship Crew (Indonesian Waters)",
        "category": "Visa Free",
        "duration": "30 days",
        "cost_visa": "FREE",
        "processing_time_normal": "Instant",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Listed in General Declaration or Crew List",
            "Vessel operates in Indonesian waters (archipelagic, territorial, EEZ)",
        ],
        "benefits": [
            "Work as captain, crew, or foreign expert on marine vessels",
            "Operations in Indonesian archipelagic waters",
            "Operations in Exclusive Economic Zone (EEZ)",
            "Tourism during shore leave",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "extendable": False,
            "convertible": False,
            "operating_areas": ["Nusantara Waters", "Territorial Sea", "Continental Shelf", "EEZ"],
            "work_allowed": True,
        },
    },
    # ==================== B SERIES - VOA ====================
    "B1": {
        "name": "B1 - Tourism",
        "category": "VOA",
        "duration": "30 days (extendable to 60)",
        "cost_visa": "IDR 500,000",
        "processing_time_normal": "Instant or 1x24h (e-VOA)",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Return or onward ticket",
            "VOA-eligible nationality",
            "Recent color passport photo",
        ],
        "benefits": [
            "Tourism and leisure activities",
            "Visiting family and friends",
            "Attending MICE events",
            "Extendable once for 30 days",
            "Convertible to ITAS via bridging visa",
            "No sponsor required",
        ],
        "metadata": {
            "series": "B",
            "entry_type": "Single",
            "extendable": True,
            "extension_count": 1,
            "extension_duration": "30 days",
            "total_max_stay": "60 days",
            "convertible": True,
            "conversion_method": "Bridging visa",
            "sponsor_required": False,
            "evoa_validity": "90 days from issuance",
            "application_methods": ["e-VOA Pre-Arrival", "Traditional VOA at airport"],
        },
    },
    "B4": {
        "name": "B4 - Government Assignment",
        "category": "VOA",
        "duration": "30 days (extendable to 60)",
        "cost_visa": "IDR 500,000",
        "processing_time_normal": "Instant or 1x24h (e-VOA)",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Return or onward ticket",
            "Official government assignment documentation",
        ],
        "benefits": [
            "Government duties and official assignments",
            "Tourism while on assignment",
            "Extendable once for 30 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "B",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "purpose": "Government Assignment",
        },
    },
    # ==================== F SERIES - VOA (RIAU ISLANDS) ====================
    "F1": {
        "name": "F1 - Tourism (Riau Islands)",
        "category": "VOA",
        "duration": "7 days",
        "cost_visa": "IDR 250,000",
        "processing_time_normal": "Instant",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Entry via designated Riau Islands seaports only",
        ],
        "benefits": [
            "Tourism in Riau Islands region",
            "Family visits",
            "MICE attendance",
            "Transit",
        ],
        "metadata": {
            "series": "F",
            "entry_type": "Single",
            "extendable": False,
            "convertible": False,
            "designated_ports": [
                "Nongsa Terminal Bahari",
                "Marina Teluk Senimba",
                "Batam Centre",
                "Citra Tri Tunas",
                "Sri Bintan Pura",
                "Bandar Bentani Telani Lagoi",
                "Tanjung Balai Karimun",
            ],
        },
    },
    "F4": {
        "name": "F4 - Government Assignment (Riau Islands)",
        "category": "VOA",
        "duration": "7 days",
        "cost_visa": "IDR 250,000",
        "processing_time_normal": "Instant",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Entry via designated Riau Islands seaports only",
            "Government assignment documentation",
        ],
        "benefits": ["Government duties in Riau Islands", "Tourism activities"],
        "metadata": {
            "series": "F",
            "entry_type": "Single",
            "extendable": False,
            "convertible": False,
            "purpose": "Government Assignment",
        },
    },
    # ==================== C SERIES - VISIT VISA ====================
    "C1": {
        "name": "C1 - Tourism",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 1,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Proof of funds (bank statement, min USD 2,000)",
            "Return ticket",
            "Recent color photo",
        ],
        "benefits": [
            "Tourism and personal development",
            "Studying tourism attractions",
            "Cruise ship travel",
            "Attending MICE as participant",
            "Business discussions/negotiations",
            "Field surveys (offices/factories)",
            "Extendable multiple times up to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "initial_stay": "60 days",
            "max_stay": "180 days",
            "extendable": True,
            "convertible": True,
            "sponsor_required": False,
        },
    },
    "C2": {
        "name": "C2 - Business",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Proof of funds (bank statement)",
            "Invitation letter from Indonesian company/institution",
        ],
        "benefits": [
            "Business meetings and negotiations",
            "Purchasing goods",
            "Signing agreements",
            "Inspecting goods at offices/factories",
            "Tourism and family visits",
            "Extendable to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": False,
            "invitation_required": True,
        },
    },
    "C3": {
        "name": "C3 - Medical Treatment",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 1,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Sponsor letter",
            "Proof of funds",
            "Hospital/institution letter confirming treatment plan",
        ],
        "benefits": [
            "Medical treatment in Indonesia",
            "Tourism and family visits",
            "Extendable to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Medical Treatment",
        },
    },
    "C4": {
        "name": "C4 - Government Assignment",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 12 months)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Invitation/statement from Government Agency",
        ],
        "benefits": [
            "Government duties",
            "Tourism and family visits",
            "Extendable up to 12 months total",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "initial_stay": "60 days",
            "max_stay": "12 months",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
        },
    },
    "C5": {
        "name": "C5 - Media and Press",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Press ID card",
            "Invitation/statement from Government Agency",
            "Interview transcripts or coverage plan letter",
        ],
        "benefits": [
            "Journalistic visits and media coverage",
            "Tourism and family visits",
            "Extendable to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "purpose": "Journalism/Media",
        },
    },
    "C5A": {
        "name": "C5A - Content Creator",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Proof of content creator status (social media profile, portfolio)",
            "Proof of funds",
        ],
        "benefits": [
            "Content creation activities",
            "Photography and videography",
            "Tourism and exploration",
            "Extendable to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "purpose": "Content Creation",
        },
    },
    "C6": {
        "name": "C6 - Social Activities",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Statement from Government/Private institution explaining activities",
        ],
        "benefits": [
            "Charity and humanitarian activities",
            "Social work",
            "Tourism and family visits",
            "Extendable to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Social Activities",
        },
    },
    "C7": {
        "name": "C7 - Arts and Culture",
        "category": "Visit Visa",
        "duration": "30 days (non-extendable)",
        "cost_visa": "IDR 1,500,000",
        "processing_time_normal": "3-5 business days",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Sponsor letter from organizer",
            "Invitation letter or contract from impresario",
        ],
        "benefits": [
            "Arts and culture performances (shows, music, theater, circus)",
            "Allowed to receive compensation/facilities for performance",
            "Tourism and family visits",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": False,
            "convertible": False,
            "sponsor_required": True,
            "compensation_allowed": True,
            "purpose": "Arts and Culture Performance",
        },
    },
    "C7A": {
        "name": "C7A - Music Performance",
        "category": "Visit Visa",
        "duration": "30 days (non-extendable)",
        "cost_visa": "IDR 1,500,000",
        "processing_time_normal": "3-5 business days",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Sponsor letter",
            "Contract or letter from impresario",
        ],
        "benefits": [
            "Music performances",
            "Allowed to receive compensation/facilities",
            "Tourism activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": False,
            "sponsor_required": True,
            "compensation_allowed": True,
            "purpose": "Music Performance",
        },
    },
    "C7B": {
        "name": "C7B - Music Performance Crew",
        "category": "Visit Visa",
        "duration": "30 days (non-extendable)",
        "cost_visa": "IDR 1,500,000",
        "processing_time_normal": "3-5 business days",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Sponsor letter from organizer",
            "Proof of crew status with performing artist",
        ],
        "benefits": [
            "Supporting foreign music performers as crew",
            "Technical and production support",
            "Tourism activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": False,
            "sponsor_required": True,
            "purpose": "Music Performance Crew",
        },
    },
    "C7C": {
        "name": "C7C - Talent and Arts",
        "category": "Visit Visa",
        "duration": "30 days (non-extendable)",
        "cost_visa": "IDR 1,500,000",
        "processing_time_normal": "3-5 business days",
        "renewable": False,
        "requirements": [
            "Passport valid for at least 6 months",
            "Sponsor letter",
            "Portfolio or proof of talent",
        ],
        "benefits": [
            "Talent shows and arts exhibitions",
            "Artistic collaborations",
            "Tourism activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": False,
            "sponsor_required": True,
            "purpose": "Talent and Arts",
        },
    },
    "C8": {
        "name": "C8 - Sports Activities",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Invitation from sports organization or event organizer",
        ],
        "benefits": [
            "Sports activities and competitions",
            "Training and practice",
            "Allowed to receive prizes/facilities",
            "Tourism and family visits",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Sports Activities",
        },
    },
    "C8A": {
        "name": "C8A - Athletes",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Sponsor letter",
            "Invitation from event organizer",
            "Proof of athlete status",
        ],
        "benefits": [
            "Non-commercial sports (government invitation, international championships)",
            "Allowed to receive prizes/facilities but not employment salary",
            "Tourism and family visits",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Athletes",
        },
    },
    "C8B": {
        "name": "C8B - Sports Officials",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Invitation from sports organization",
            "Proof of official status",
        ],
        "benefits": [
            "Officiating sports events",
            "Refereeing and judging",
            "Training officials",
            "Tourism activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Sports Officials",
        },
    },
    "C9": {
        "name": "C9 - Short Study",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Proof of registration/student status from institution",
        ],
        "benefits": [
            "Comparative study",
            "Short courses and training",
            "Extendable to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Short Study/Training",
        },
    },
    "C9A": {
        "name": "C9A - Religious Training",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Letter from religious institution",
        ],
        "benefits": [
            "Religious education and training",
            "Spiritual retreats",
            "Tourism activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Religious Training",
        },
    },
    "C9B": {
        "name": "C9B - Indonesian Language Training",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Enrollment letter from language school",
        ],
        "benefits": [
            "Indonesian language courses (Bahasa Indonesia)",
            "Cultural immersion",
            "Tourism activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Language Training",
        },
    },
    "C10": {
        "name": "C10 - Business Speaker",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Invitation letter detailing agenda",
        ],
        "benefits": [
            "Speaker, lecturer, or presenter at MICE events",
            "Allowed to receive honorarium/compensation",
            "Tourism and family visits",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "compensation_allowed": True,
            "purpose": "Business Speaker/Lecturer",
        },
    },
    "C10A": {
        "name": "C10A - Religious Speaker",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Invitation from religious organization",
        ],
        "benefits": [
            "Religious speaking engagements",
            "Sermons and teachings",
            "Tourism activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Religious Speaker",
        },
    },
    "C11": {
        "name": "C11 - Product Promotion",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": ["Passport valid for at least 6 months", "Invitation from event organizer"],
        "benefits": [
            "Participating in MICE events as exhibitor",
            "Marketing goods or services",
            "Extendable to 180 days",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Exhibition/Product Promotion",
            "restrictions": ["Prohibited from direct retail sales"],
        },
    },
    "C11A": {
        "name": "C11A - Product Promotion (Variant)",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": ["Passport valid for at least 6 months", "Invitation from organizer"],
        "benefits": ["Product demonstrations", "Trade show participation", "Marketing activities"],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Product Promotion Variant",
        },
    },
    "C12": {
        "name": "C12 - Pre-Investment",
        "category": "Visit Visa",
        "duration": "60-180 days (extendable to 12 months)",
        "cost_visa": "IDR 3,000,000 (60d) / IDR 4,000,000 (180d)",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Proof of funds (min USD 2,000)",
            "Business relationship/intent documentation",
        ],
        "benefits": [
            "Pre-investment visits",
            "Starting a business",
            "Field surveys and feasibility studies",
            "Extendable up to 12 months",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "initial_stay_options": ["60 days", "180 days"],
            "max_stay": "12 months",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Pre-Investment",
        },
    },
    "C13": {
        "name": "C13 - Crew Joining Transport",
        "category": "Visit Visa",
        "duration": "60 days (extendable)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Letter stating intent to join vessel",
        ],
        "benefits": [
            "Joining transport vehicle (ship/vessel) in Indonesian territory",
            "Extendable",
            "Convertible to ITAS",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Vessel Joiner",
        },
    },
    "C14": {
        "name": "C14 - Film Production",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Filming Permit from relevant Government Agency",
        ],
        "benefits": [
            "Filmmaking and music videos",
            "Reality shows and documentaries",
            "TV/radio production",
            "Using Indonesian locations",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "filming_permit_required": True,
            "purpose": "Film Production",
        },
    },
    "C15": {
        "name": "C15 - Emergency Response",
        "category": "Visit Visa",
        "duration": "60 days (extendable)",
        "cost_visa": "IDR 3,000,000",
        "processing_time_normal": "Expedited",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Statement of urgency explaining need for foreign expert",
        ],
        "benefits": [
            "Emergency and urgent work",
            "Natural disaster recovery",
            "Machine repair",
            "Crisis management",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Emergency Work",
        },
    },
    "C16": {
        "name": "C16 - Industry Instructor",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 3,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Invitation from company/institution",
        ],
        "benefits": [
            "Guidance and counseling in industrial technology",
            "Innovation and application training",
            "Extendable to 180 days",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Industrial Instructor",
        },
    },
    "C17": {
        "name": "C17 - Audit and Quality Control",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 3,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": ["Passport valid for at least 6 months", "Letter from parent company"],
        "benefits": [
            "Auditing company branches",
            "Production quality control",
            "Inspection activities",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Audit/Quality Control",
        },
    },
    "C18": {
        "name": "C18 - Work Trial",
        "category": "Visit Visa",
        "duration": "90 days (non-extendable)",
        "cost_visa": "IDR 4,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": False,
        "requirements": ["Passport valid for at least 6 months", "Invitation for competency test"],
        "benefits": ["Testing proficiency/skills for work", "Trial employment period"],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "max_stay": "90 days",
            "extendable": False,
            "convertible": False,
            "sponsor_required": True,
            "purpose": "Competency Test/Work Trial",
        },
    },
    "C19": {
        "name": "C19 - After-Sales Service",
        "category": "Visit Visa",
        "duration": "60 days (extendable)",
        "cost_visa": "IDR 3,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Proof of product sale to Indonesian customer",
        ],
        "benefits": [
            "After-sales service for goods/products",
            "Customer support",
            "Product maintenance",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "After-Sales Service",
        },
    },
    "C20": {
        "name": "C20 - Installation and Repair",
        "category": "Visit Visa",
        "duration": "60 days (extendable)",
        "cost_visa": "IDR 3,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Purchase agreement for machinery",
        ],
        "benefits": [
            "Machinery installation",
            "Equipment repair",
            "Technical support as part of purchase agreement",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Installation/Repair",
        },
    },
    "C21": {
        "name": "C21 - Training Instructor",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 3,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Invitation from training institution",
        ],
        "benefits": [
            "Conducting training sessions",
            "Skills transfer",
            "Professional development instruction",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Training Instructor",
        },
    },
    "C22": {
        "name": "C22 - Internship",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Internship agreement with Indonesian company",
        ],
        "benefits": ["Professional internship", "Work experience", "Extendable to 180 days"],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Internship",
        },
    },
    "C22A": {
        "name": "C22A - Academic Internship",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Letter from academic institution",
        ],
        "benefits": ["Academic internship programs", "University exchange", "Research internships"],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Academic Internship",
        },
    },
    "C22B": {
        "name": "C22B - Skills Development",
        "category": "Visit Visa",
        "duration": "60 days (extendable to 180)",
        "cost_visa": "IDR 2,000,000",
        "processing_time_normal": "3-5 business days",
        "renewable": True,
        "requirements": [
            "Passport valid for at least 6 months",
            "Enrollment in skills development program",
        ],
        "benefits": [
            "Skills development programs",
            "Vocational training",
            "Professional certification courses",
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "extendable": True,
            "convertible": True,
            "sponsor_required": True,
            "purpose": "Skills Development",
        },
    },
}


async def integrate_visas():
    """Integrate all A-C series visas with complete data."""
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    try:
        print("=" * 60)
        print("VISA INTEGRATION: A-C Series Complete Data")
        print("=" * 60)

        updated = 0
        inserted = 0

        for code, data in VISA_DATA.items():
            # Check if exists
            existing = await conn.fetchval("SELECT id FROM visa_types WHERE code = $1", code)

            if existing:
                # Update
                await conn.execute(
                    """
                    UPDATE visa_types SET
                        name = $2,
                        category = $3,
                        duration = $4,
                        cost_visa = $5,
                        processing_time_normal = $6,
                        renewable = $7,
                        requirements = $8,
                        benefits = $9,
                        metadata = $10,
                        last_updated = NOW()
                    WHERE code = $1
                    """,
                    code,
                    data["name"],
                    data["category"],
                    data["duration"],
                    data["cost_visa"],
                    data.get("processing_time_normal", "3-5 business days"),
                    data["renewable"],
                    data["requirements"],
                    data["benefits"],
                    json.dumps(data["metadata"]),
                )
                print(f"  ✓ Updated: {data['name']}")
                updated += 1
            else:
                # Insert
                await conn.execute(
                    """
                    INSERT INTO visa_types (
                        code, name, category, duration, cost_visa,
                        processing_time_normal, renewable, foreign_eligible,
                        requirements, benefits, metadata, created_at, last_updated
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                    """,
                    code,
                    data["name"],
                    data["category"],
                    data["duration"],
                    data["cost_visa"],
                    data.get("processing_time_normal", "3-5 business days"),
                    data["renewable"],
                    True,
                    data["requirements"],
                    data["benefits"],
                    json.dumps(data["metadata"]),
                )
                print(f"  + Inserted: {data['name']}")
                inserted += 1

        print("\n" + "=" * 60)
        print(f"✅ Updated: {updated} | Inserted: {inserted} | Total: {updated + inserted}")
        print("=" * 60)

        # Show summary by series
        print("\n📋 VISA SUMMARY BY SERIES:")
        for series, name in [
            ("A", "Visa Free"),
            ("B", "VOA"),
            ("F", "VOA Short"),
            ("C", "Visit Visa"),
        ]:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM visa_types WHERE code LIKE $1", f"{series}%"
            )
            print(f"  {series} ({name}): {count} visas")

        # Show all visas
        print("\n📋 ALL A-C SERIES VISAS:")
        print("-" * 70)
        rows = await conn.fetch(
            """
            SELECT code, name, category, duration, cost_visa
            FROM visa_types
            WHERE code ~ '^[ABFC]'
            ORDER BY
                CASE
                    WHEN code LIKE 'A%' THEN 1
                    WHEN code LIKE 'B%' THEN 2
                    WHEN code LIKE 'F%' THEN 3
                    WHEN code LIKE 'C%' THEN 4
                END,
                code
            """
        )

        current = ""
        for row in rows:
            s = row["code"][0]
            if s != current:
                current = s
                names = {"A": "Visa Free", "B": "VOA", "F": "VOA Short", "C": "Visit Visa"}
                print(f"\n=== {s} Series - {names.get(s, '')} ===")
            print(f"  {row['code']:6} | {row['name'][:40]:40} | {row['cost_visa']}")

        print(f"\nTotal: {len(rows)} visas in A/B/F/C series")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(integrate_visas())

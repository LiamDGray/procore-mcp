"""Synthetic Construction Sandbox Engine for Procore MCP zero-key demonstration."""

from __future__ import annotations

import re
from typing import Any

from procore_mcp.safety import (
    FORBIDDEN_MUTATION_STATUSES,
    SafetyInvariantViolation,
    normalize_status_string,
)


class DemoSandbox:
    """Stateful in-memory synthetic construction sandbox engine for Aegis Tower."""

    def __init__(self) -> None:
        self.companies: list[dict[str, Any]] = [
            {
                "id": 1,
                "name": "Aegis Construction Group Inc.",
                "is_active": True,
            }
        ]

        self.projects: list[dict[str, Any]] = [
            {
                "id": 101,
                "name": "Aegis Tower",
                "status": "Active",
                "is_active": True,
                "company_id": 1,
                "address": "742 Evergreen Terrace, Seattle, WA",
            }
        ]

        self.vendors: list[dict[str, Any]] = [
            {"id": 101, "name": "Metro Concrete Solutions", "trade": "Cast-in-Place Concrete"},
            {"id": 102, "name": "Apex Structural Steel Fabricators", "trade": "Structural Steel"},
            {"id": 103, "name": "Helix Mechanical Contractors", "trade": "HVAC & Plumbing"},
            {"id": 104, "name": "Spark Electric Systems", "trade": "Electrical & Low Voltage"},
            {
                "id": 105,
                "name": "Pinnacle Glazing & Curtainwall Inc.",
                "trade": "Curtainwall & Glazing",
            },
            {"id": 106, "name": "Titan Foundation & Earthworks", "trade": "Excavation & Shoring"},
            {"id": 107, "name": "Cascade Fire Suppression LLC", "trade": "Fire Protection"},
            {"id": 108, "name": "Otis Elevation Systems", "trade": "Elevators"},
        ]

        self.directory_users: list[dict[str, Any]] = [
            {
                "id": 1,
                "name": "Sarah Chen",
                "email": "sarah.chen@aegisconstruction.com",
                "job_title": "Senior Project Manager",
            },
            {
                "id": 2,
                "name": "Marcus Vance",
                "email": "marcus.vance@aegisconstruction.com",
                "job_title": "Lead Superintendent",
            },
            {
                "id": 3,
                "name": "Elena Rostova",
                "email": "erostova@mka-engineers.com",
                "job_title": "Structural Engineer (EOR)",
            },
            {
                "id": 4,
                "name": "David Kalu",
                "email": "dkalu@callisonrtkl.com",
                "job_title": "Architect of Record",
            },
            {
                "id": 5,
                "name": "James Thornton",
                "email": "jthornton@helixmech.com",
                "job_title": "MEP Project Engineer",
            },
            {
                "id": 6,
                "name": "Maria Rodriguez",
                "email": "mrodriguez@aegisconstruction.com",
                "job_title": "Safety Director",
            },
            {
                "id": 7,
                "name": "Keith Bradley",
                "email": "kbradley@sparkelectric.com",
                "job_title": "Electrical Superintendent",
            },
        ]

        # CSI MasterFormat 2018/2020 Budget Line Items (Exact sum: $85,400,000.00)
        self.budget_items: list[dict[str, Any]] = [
            {
                "id": 1,
                "cost_code": "01-1000 - Summary of Work",
                "original_budget": 3200000.0,
                "approved_changes": 0.0,
                "revised_budget": 3200000.0,
            },
            {
                "id": 2,
                "cost_code": "01-3100 - Project Management and Coordination",
                "original_budget": 1800000.0,
                "approved_changes": 0.0,
                "revised_budget": 1800000.0,
            },
            {
                "id": 3,
                "cost_code": "01-5000 - Temporary Facilities and Controls",
                "original_budget": 1400000.0,
                "approved_changes": 0.0,
                "revised_budget": 1400000.0,
            },
            {
                "id": 4,
                "cost_code": "02-4100 - Demolition and Abatement",
                "original_budget": 900000.0,
                "approved_changes": 0.0,
                "revised_budget": 900000.0,
            },
            {
                "id": 5,
                "cost_code": "03-3000 - Cast-in-Place Concrete",
                "original_budget": 18500000.0,
                "approved_changes": 0.0,
                "revised_budget": 18500000.0,
            },
            {
                "id": 6,
                "cost_code": "04-2000 - Unit Masonry",
                "original_budget": 1200000.0,
                "approved_changes": 0.0,
                "revised_budget": 1200000.0,
            },
            {
                "id": 7,
                "cost_code": "05-1200 - Structural Steel Framing",
                "original_budget": 14600000.0,
                "approved_changes": 0.0,
                "revised_budget": 14600000.0,
            },
            {
                "id": 8,
                "cost_code": "06-1000 - Rough Carpentry & Architectural Millwork",
                "original_budget": 1100000.0,
                "approved_changes": 0.0,
                "revised_budget": 1100000.0,
            },
            {
                "id": 9,
                "cost_code": "07-1000 - Damp-proofing and Waterproofing",
                "original_budget": 2400000.0,
                "approved_changes": 0.0,
                "revised_budget": 2400000.0,
            },
            {
                "id": 10,
                "cost_code": "07-5000 - Membrane Roofing",
                "original_budget": 1800000.0,
                "approved_changes": 0.0,
                "revised_budget": 1800000.0,
            },
            {
                "id": 11,
                "cost_code": "08-4400 - Curtain Wall and Glazed Assemblies",
                "original_budget": 10500000.0,
                "approved_changes": 0.0,
                "revised_budget": 10500000.0,
            },
            {
                "id": 12,
                "cost_code": "08-7100 - Door Hardware & Security Access",
                "original_budget": 800000.0,
                "approved_changes": 0.0,
                "revised_budget": 800000.0,
            },
            {
                "id": 13,
                "cost_code": "09-2200 - Framing and Gypsum Board Assemblies",
                "original_budget": 4200000.0,
                "approved_changes": 0.0,
                "revised_budget": 4200000.0,
            },
            {
                "id": 14,
                "cost_code": "09-6500 - Resilient Flooring and Finishes",
                "original_budget": 1900000.0,
                "approved_changes": 0.0,
                "revised_budget": 1900000.0,
            },
            {
                "id": 15,
                "cost_code": "14-2000 - Elevators and Conveying Systems",
                "original_budget": 5800000.0,
                "approved_changes": 0.0,
                "revised_budget": 5800000.0,
            },
            {
                "id": 16,
                "cost_code": "21-1300 - Fire Suppression Sprinkler Systems",
                "original_budget": 1600000.0,
                "approved_changes": 0.0,
                "revised_budget": 1600000.0,
            },
            {
                "id": 17,
                "cost_code": "22-1000 - Plumbing Piping and Fixtures",
                "original_budget": 3400000.0,
                "approved_changes": 0.0,
                "revised_budget": 3400000.0,
            },
            {
                "id": 18,
                "cost_code": "23-0000 - Heating, Ventilating, and Air Conditioning",
                "original_budget": 5400000.0,
                "approved_changes": 0.0,
                "revised_budget": 5400000.0,
            },
            {
                "id": 19,
                "cost_code": "26-0000 - Electrical Distribution and Lighting",
                "original_budget": 4500000.0,
                "approved_changes": 0.0,
                "revised_budget": 4500000.0,
            },
            {
                "id": 20,
                "cost_code": "31-2000 - Earth Moving and Deep Foundations",
                "original_budget": 400000.0,
                "approved_changes": 0.0,
                "revised_budget": 400000.0,
            },
        ]

        self.cost_codes: list[dict[str, Any]] = [
            {
                "id": idx,
                "code": item["cost_code"].split(" - ")[0],
                "description": item["cost_code"].split(" - ")[1],
            }
            for idx, item in enumerate(self.budget_items, start=1)
        ]

        # 24 Realistic RFIs (Structural, MEP, Architectural)
        self.rfis: list[dict[str, Any]] = [
            {
                "id": 1,
                "number": "RFI-001",
                "subject": "L4 Core Wall Rebar Congestion at Boundary Element Grid C-3",
                "status": "Open",
                "due_date": "2026-03-15",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Severe rebar congestion between #11 vertical bars and "
                    "post-tension anchor heads at grid C-3. Requesting engineer "
                    "approval to bundle bars or substitute mechanical couplers."
                ),
                "responses": [
                    {
                        "id": 101,
                        "body": (
                            "Couplers are approved provided stagger requirement of 24 "
                            "inches per ACI 318-19 Section 25.5 is maintained."
                        ),
                        "responder": {"name": "Elena Rostova"},
                    }
                ],
            },
            {
                "id": 2,
                "number": "RFI-002",
                "subject": "Post-Tension Tendon Drape Clearance at Elevator Core Penetrations",
                "status": "Closed",
                "due_date": "2026-02-28",
                "ball_in_court": "Marcus Vance",
                "question": (
                    "PT cable profile conflicts with sleeve penetrations for "
                    "elevator governor cables on Level 12. Clarify drape profile "
                    "adjustment."
                ),
                "responses": [
                    {
                        "id": 102,
                        "body": (
                            "Drape profile adjusted 3 inches to the west per revised "
                            "structural sketch SK-PT-12."
                        ),
                        "responder": {"name": "Elena Rostova"},
                    }
                ],
            },
            {
                "id": 3,
                "number": "RFI-003",
                "subject": "Transfer Girder TG-2 Moment Connection Weld Detail",
                "status": "Open",
                "due_date": "2026-03-20",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Detail 4/S5.01 shows CJP weld on 3-inch flange of column C2. "
                    "Welding access hole dimensions conflict with AISC 360-16 Table "
                    "1-1."
                ),
                "responses": [],
            },
            {
                "id": 4,
                "number": "RFI-004",
                "subject": "Slab Opening Trim Rebar at Mechanical Shaft Level 8",
                "status": "Open",
                "due_date": "2026-03-18",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Mechanical chase enlarged by 14 inches to accommodate dual "
                    "return air risers. Specify diagonal trim rebar schedule for "
                    "slab edge."
                ),
                "responses": [],
            },
            {
                "id": 5,
                "number": "RFI-005",
                "subject": (
                    "Foundation Mat Pour Joint Keyway vs Hydrophilic Waterstop Configuration"
                ),
                "status": "Closed",
                "due_date": "2026-02-14",
                "ball_in_court": "Sarah Chen",
                "question": (
                    "Confirm if cold joint at Pour 3 of foundation mat requires "
                    "expanded metal mesh keyway in addition to bentonite waterstop."
                ),
                "responses": [
                    {
                        "id": 105,
                        "body": (
                            "Both hydrophilic waterstop and keyed construction joint "
                            "are mandatory per spec section 03 30 00.3.4."
                        ),
                        "responder": {"name": "Elena Rostova"},
                    }
                ],
            },
            {
                "id": 6,
                "number": "RFI-006",
                "subject": "Structural Steel Baseplate Shim Pocket Tolerances at Grid E-5",
                "status": "Open",
                "due_date": "2026-03-22",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Tower crane foundation anchor bolt cluster rotated 1.2 degrees "
                    "during placement. Review baseplate slotting proposal."
                ),
                "responses": [],
            },
            {
                "id": 7,
                "number": "RFI-007",
                "subject": "Shear Stud Layout Conflict with Metal Deck Flutes on Level 12",
                "status": "Open",
                "due_date": "2026-03-25",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Composite beam studs fall directly on rib valleys where deck "
                    "overlaps occur. Advise on transverse spacing adjustment."
                ),
                "responses": [],
            },
            {
                "id": 8,
                "number": "RFI-008",
                "subject": (
                    "Main HVAC Supply Duct Clash with 8-inch Chilled Water Pipe at Level 6 Corridor"
                ),
                "status": "Open",
                "due_date": "2026-03-16",
                "ball_in_court": "James Thornton",
                "question": (
                    "BIM coordination shows 60x24 supply duct clashing with primary "
                    "8-inch chilled water riser elbow. Ceiling height restriction "
                    "prevents dropping duct."
                ),
                "responses": [
                    {
                        "id": 108,
                        "body": (
                            "Mechanical engineering approved splitting into two 36x24 "
                            "ducts transitioning around pipe elbow."
                        ),
                        "responder": {"name": "James Thornton"},
                    }
                ],
            },
            {
                "id": 9,
                "number": "RFI-009",
                "subject": (
                    "Electrical Conduit Run Conflict with Gravity Storm Drain in Electrical Room B1"
                ),
                "status": "Closed",
                "due_date": "2026-02-22",
                "ball_in_court": "Keith Bradley",
                "question": (
                    "NEC 110.26 dedicated equipment space rule violated by 6-inch "
                    "storm drain passing above switchgear MSB-1. Rerouting path "
                    "requested."
                ),
                "responses": [
                    {
                        "id": 109,
                        "body": (
                            "Storm drain relocated outside of electrical room perimeter "
                            "wall per plumbing sketch SK-P-04."
                        ),
                        "responder": {"name": "David Kalu"},
                    }
                ],
            },
            {
                "id": 10,
                "number": "RFI-010",
                "subject": "Fire Sprinkler Main Routing Through Web Opening of Steel Beam W24x76",
                "status": "Open",
                "due_date": "2026-03-19",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Requesting engineering permission to core 6-inch diameter "
                    "penetration through web of W24x76 at mid-span for 4-inch "
                    "sprinkler main."
                ),
                "responses": [],
            },
            {
                "id": 11,
                "number": "RFI-011",
                "subject": "Smoke Exhaust Fan Duct Penetration at Stair 1 Enclosure",
                "status": "Open",
                "due_date": "2026-03-24",
                "ball_in_court": "David Kalu",
                "question": (
                    "IBC 1023.5 restricts penetrations through exit stair "
                    "enclosures. Verify if combination fire/smoke damper assembly "
                    "meets building code requirements."
                ),
                "responses": [],
            },
            {
                "id": 12,
                "number": "RFI-012",
                "subject": "Domestic Hot Water Recirculation Return Sizing at Level 18",
                "status": "Closed",
                "due_date": "2026-02-18",
                "ball_in_court": "James Thornton",
                "question": (
                    "Hydraulic pressure loss calculation shows 3/4-inch return line "
                    "inadequate for 20 gpm balancing valve design. Confirm upsizing "
                    "to 1-1/4 inch."
                ),
                "responses": [
                    {
                        "id": 112,
                        "body": "Upsize approved. Revised plumbing schedule issued.",
                        "responder": {"name": "James Thornton"},
                    }
                ],
            },
            {
                "id": 13,
                "number": "RFI-013",
                "subject": "Primary Electrical Switchgear Feeder Vault Invert Elevation Conflict",
                "status": "Open",
                "due_date": "2026-03-21",
                "ball_in_court": "Keith Bradley",
                "question": (
                    "Seattle City Light utility conduit bank enters vault 18 inches "
                    "lower than contract drawings depict, hitting perimeter footing "
                    "drain tile."
                ),
                "responses": [],
            },
            {
                "id": 14,
                "number": "RFI-014",
                "subject": "Condenser Water Riser Expansion Joint Anchor Load Verification",
                "status": "Open",
                "due_date": "2026-03-27",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Axial anchor load of 18,500 lbs from 12-inch condenser water "
                    "thermal expansion exceeds concrete insert allowable capacity "
                    "on Level 15 slab."
                ),
                "responses": [],
            },
            {
                "id": 15,
                "number": "RFI-015",
                "subject": "Curtain Wall Thermal Break Detail at Spandrel Panel Level 10",
                "status": "Open",
                "due_date": "2026-03-17",
                "ball_in_court": "David Kalu",
                "question": (
                    "Architectural drawing A4.12 detail 6 does not match curtain "
                    "wall shop drawing CW-10. Verify continuous insulation vapor "
                    "barrier seal."
                ),
                "responses": [],
            },
            {
                "id": 16,
                "number": "RFI-016",
                "subject": "2-Hour Fire-Rated Joint Sealant System at Floor Edge to Curtain Wall",
                "status": "Closed",
                "due_date": "2026-02-10",
                "ball_in_court": "Maria Rodriguez",
                "question": (
                    "UL Listing HW-D-1087 calls for 4-pcf mineral wool with 50% "
                    "compression. Verify compatibility with seismic mullion "
                    "movement clips."
                ),
                "responses": [
                    {
                        "id": 116,
                        "body": (
                            "System HW-D-1087 verified compatible with 1.5-inch lateral "
                            "drift requirements per UL report 2490."
                        ),
                        "responder": {"name": "David Kalu"},
                    }
                ],
            },
            {
                "id": 17,
                "number": "RFI-017",
                "subject": (
                    "Door Frame Rough Opening Dimensions for Acoustic Double Doors Room 302"
                ),
                "status": "Open",
                "due_date": "2026-03-26",
                "ball_in_court": "David Kalu",
                "question": (
                    "STC 55 acoustic gasketing package requires 1/2-inch wider "
                    "frame throat depth than specified on door schedule."
                ),
                "responses": [],
            },
            {
                "id": 18,
                "number": "RFI-018",
                "subject": "Podium Terrace Elastomeric Waterproofing Transition at Parapet Cap",
                "status": "Closed",
                "due_date": "2026-02-15",
                "ball_in_court": "David Kalu",
                "question": (
                    "Waterproofing manufacturer requires minimum 8-inch vertical "
                    "flashing turn-up, but parapet height at grid A-1 is only 6 "
                    "inches."
                ),
                "responses": [
                    {
                        "id": 118,
                        "body": (
                            "Framing sub to build up parapet top plate 3 inches using "
                            "treated wood blocking prior to flashing installation."
                        ),
                        "responder": {"name": "David Kalu"},
                    }
                ],
            },
            {
                "id": 19,
                "number": "RFI-019",
                "subject": "Main Lobby Feature Wood Slat Ceiling Suspension Seismic Bracing",
                "status": "Open",
                "due_date": "2026-03-28",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Seismic Design Category D requirements require rigid strut "
                    "bracing at 12 ft on center. Confirm anchorage into underside "
                    "of post-tensioned slab."
                ),
                "responses": [],
            },
            {
                "id": 20,
                "number": "RFI-020",
                "subject": (
                    "High-Strength Anchor Bolt Embedment Depth Verification at Level 1 Column C2"
                ),
                "status": "Closed",
                "due_date": "2026-02-05",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Grade 105 anchor rods require 36-inch embedment depth. Confirm "
                    "rebar cage clearance at column pier pier-cap junction."
                ),
                "responses": [
                    {
                        "id": 120,
                        "body": "Embedment depth verified acceptable per calculation calc-C2-01.",
                        "responder": {"name": "Elena Rostova"},
                    }
                ],
            },
            {
                "id": 21,
                "number": "RFI-021",
                "subject": "ADA Clearance Conflict at Level 2 Restroom Lavatory Millwork",
                "status": "Open",
                "due_date": "2026-03-23",
                "ball_in_court": "David Kalu",
                "question": (
                    "Knee clearance depth measures 25 inches vs required 27 inches "
                    "under ICC A117.1 Section 606.3 due to pipe trap insulation "
                    "wrap."
                ),
                "responses": [],
            },
            {
                "id": 22,
                "number": "RFI-022",
                "subject": "Precast Stair Stringer Connection Tolerance at Landing 5",
                "status": "Open",
                "due_date": "2026-03-29",
                "ball_in_court": "Elena Rostova",
                "question": (
                    "Precast stair flight 5 embed pocket is 1/2-inch lower than "
                    "specified elevation. Propose steel shim pack configuration."
                ),
                "responses": [],
            },
            {
                "id": 23,
                "number": "RFI-023",
                "subject": "VAV Box Clearance for Filter Service Access in Low Ceiling Zone 4",
                "status": "Open",
                "due_date": "2026-03-30",
                "ball_in_court": "James Thornton",
                "question": (
                    "Ceiling access hatch location conflicts with bottom flange of "
                    "beam B-14. Shift hatch or swap to bottom-access VAV unit."
                ),
                "responses": [],
            },
            {
                "id": 24,
                "number": "RFI-024",
                "subject": "Roof Paver Pedestal Height Adjustment for Positive Drainage Slopes",
                "status": "Open",
                "due_date": "2026-03-31",
                "ball_in_court": "David Kalu",
                "question": (
                    "Tapered roof insulation slope creates varying pedestal heights "
                    "from 2 inches to 9 inches. Confirm leveling shim system."
                ),
                "responses": [],
            },
        ]

        # 16 Realistic Submittals
        self.submittals: list[dict[str, Any]] = [
            {
                "id": 1,
                "number": "SUB-001",
                "title": "Ready-Mix Concrete High Performance Mix Designs 8000 PSI",
                "status": "Approved",
                "spec_section": "03 30 00 - Cast-in-Place Concrete",
                "description": (
                    "8,000 PSI high-early strength concrete mix design with 30% "
                    "slag cement replacement for columns and core walls."
                ),
                "ball_in_court": "Elena Rostova",
                "type": "Product Data & Mix Design",
            },
            {
                "id": 2,
                "number": "SUB-002",
                "title": "Rebar Shop Drawings Levels 1-5 Core Wall Boundary Elements",
                "status": "Approved as Noted",
                "spec_section": "03 20 00 - Concrete Reinforcing",
                "description": (
                    "Detailed shop drawings and placement lists for Grade 60 and "
                    "Grade 80 reinforcing steel."
                ),
                "ball_in_court": "Marcus Vance",
                "type": "Shop Drawings",
            },
            {
                "id": 3,
                "number": "SUB-003",
                "title": "Structural Steel Anchor Rod Placement Plan & Mill Test Reports",
                "status": "Approved",
                "spec_section": "05 12 00 - Structural Steel Framing",
                "description": (
                    "Certified mill test reports and anchor bolt template "
                    "layouts for podium transfer framing."
                ),
                "ball_in_court": "Elena Rostova",
                "type": "Certificates & Test Reports",
            },
            {
                "id": 4,
                "number": "SUB-004",
                "title": "Composite Steel Floor Decking Shop Drawings Level 6-20",
                "status": "Approved",
                "spec_section": "05 31 00 - Steel Decking",
                "description": (
                    "3-inch 20-gauge galvanized composite deck layout with pour "
                    "stops and closure plates."
                ),
                "ball_in_court": "Apex Structural Steel",
                "type": "Shop Drawings",
            },
            {
                "id": 5,
                "number": "SUB-005",
                "title": "Self-Adhering Sheet Waterproofing Product Data & 20-Yr Warranty",
                "status": "Approved",
                "spec_section": "07 13 00 - Sheet Waterproofing",
                "description": (
                    "Rubberized asphalt membrane waterproofing for below-grade "
                    "foundation walls with protection board."
                ),
                "ball_in_court": "David Kalu",
                "type": "Product Data",
            },
            {
                "id": 6,
                "number": "SUB-006",
                "title": "Thermoplastic Membrane Roofing Wind Uplift Calculations",
                "status": "Pending Review",
                "spec_section": "07 54 00 - Thermoplastic Membrane Roofing",
                "description": (
                    "80-mil PVC roof membrane system with FM 1-90 wind uplift "
                    "engineering calculations."
                ),
                "ball_in_court": "David Kalu",
                "type": "Engineering Calculations",
            },
            {
                "id": 7,
                "number": "SUB-007",
                "title": "Unitized Curtain Wall Structural Wind Load Engineering Calculations",
                "status": "Approved as Noted",
                "spec_section": "08 44 00 - Curtain Wall and Glazed Assemblies",
                "description": (
                    "Structural calculations stamped by WA PE for 45 PSF "
                    "positive and negative wind loads."
                ),
                "ball_in_court": "Elena Rostova",
                "type": "Engineering Calculations",
            },
            {
                "id": 8,
                "number": "SUB-008",
                "title": "Curtain Wall Glass Acoustic & Thermal Mockup Test Reports",
                "status": "Approved",
                "spec_section": "08 44 01 - Curtain Wall Testing",
                "description": (
                    "AAMA 501.1 dynamic water penetration and ASTM E90 acoustic "
                    "transmission loss laboratory reports."
                ),
                "ball_in_court": "David Kalu",
                "type": "Test Reports",
            },
            {
                "id": 9,
                "number": "SUB-009",
                "title": "Architectural Finish Hardware Schedule and Master Keying System",
                "status": "Open",
                "spec_section": "08 71 00 - Door Hardware",
                "description": (
                    "Complete hardware sets, mortise locks, panic devices, and "
                    "electronic access electrified hinges."
                ),
                "ball_in_court": "David Kalu",
                "type": "Schedule",
            },
            {
                "id": 10,
                "number": "SUB-010",
                "title": "Cold-Formed Metal Framing Deflection Track Shop Drawings",
                "status": "Approved",
                "spec_section": "09 22 00 - Framing and Gypsum Board Assemblies",
                "description": (
                    "Slotted deflection track calculations for 1.0-inch "
                    "inter-story drift and floor deflection."
                ),
                "ball_in_court": "Marcus Vance",
                "type": "Shop Drawings",
            },
            {
                "id": 11,
                "number": "SUB-011",
                "title": "Traction Passenger Elevator Cab Finishes & Hoistway Reactions",
                "status": "Open",
                "spec_section": "14 20 00 - Elevators and Conveying Systems",
                "description": (
                    "700 FPM destination dispatch passenger elevator layout, "
                    "machine room reactions, and cab interior package."
                ),
                "ball_in_court": "Otis Elevation Systems",
                "type": "Shop Drawings",
            },
            {
                "id": 12,
                "number": "SUB-012",
                "title": "Fire Suppression Sprinkler Hydraulic Calculations & Seismic Bracing",
                "status": "Approved",
                "spec_section": "21 13 00 - Fire Suppression Sprinkler Systems",
                "description": (
                    "NFPA 13 hydraulic calculations and sway bracing shop "
                    "drawings stamped by Fire Protection PE."
                ),
                "ball_in_court": "Cascade Fire Suppression",
                "type": "Engineering Calculations",
            },
            {
                "id": 13,
                "number": "SUB-013",
                "title": "Cast Iron Drainage Pipe & Cleanout Shop Drawings",
                "status": "Approved",
                "spec_section": "22 10 00 - Plumbing Piping and Fixtures",
                "description": (
                    "No-hub cast iron soil pipe fittings, roof drain bodies, and "
                    "cleanout access panel details."
                ),
                "ball_in_court": "James Thornton",
                "type": "Product Data",
            },
            {
                "id": 14,
                "number": "SUB-014",
                "title": "Roof-Mounted Air Handling Units (AHU-1 & AHU-2) Sound Curves",
                "status": "Approved as Noted",
                "spec_section": "23 00 00 - HVAC Systems",
                "description": (
                    "45,000 CFM custom double-wall air handling unit submittals "
                    "with sound power level decibel curves."
                ),
                "ball_in_court": "James Thornton",
                "type": "Product Data",
            },
            {
                "id": 15,
                "number": "SUB-015",
                "title": "Main Low Voltage Switchgear Arc Flash Coordination Study",
                "status": "Open",
                "spec_section": "26 00 00 - Electrical Distribution",
                "description": (
                    "4000A 480/277V main switchboard breaker trip settings and "
                    "IEEE 1584 arc flash incident energy study."
                ),
                "ball_in_court": "Keith Bradley",
                "type": "Engineering Study",
            },
            {
                "id": 16,
                "number": "SUB-016",
                "title": "Architectural LED Lighting Fixture Schedule & Photometrics",
                "status": "Approved",
                "spec_section": "26 51 00 - Interior Lighting",
                "description": (
                    "0-10V dimmable architectural linear LED fixture schedule, "
                    "driver cuts, and emergency battery packs."
                ),
                "ball_in_court": "David Kalu",
                "type": "Schedule",
            },
        ]

        # 11 Realistic Change Events
        self.change_events: list[dict[str, Any]] = [
            {
                "id": 1,
                "event_number": "CE-001",
                "title": "Unforeseen Subsurface Glacial Till Boulder Obstruction",
                "status": "Approved",
                "description": (
                    "Massive glacial erratic boulders encountered during "
                    "basement shoring drilling requiring core barrel rock "
                    "extraction."
                ),
                "grand_total": 42500.0,
            },
            {
                "id": 2,
                "event_number": "CE-002",
                "title": "Structural Beam Reinforcement per RFI-003 Moment Connection",
                "status": "Open",
                "description": (
                    "Addition of stiffener plates and ultrasonic testing for "
                    "column C2 transfer girder connection."
                ),
                "grand_total": 18200.0,
            },
            {
                "id": 3,
                "event_number": "CE-003",
                "title": "City Inspector Mandated Fire Smoke Damper Additions on Floors 4-8",
                "status": "Approved",
                "description": (
                    "Seattle DCI mandated four additional combination fire/smoke "
                    "dampers in corridor shaft penetrations."
                ),
                "grand_total": 36400.0,
            },
            {
                "id": 4,
                "event_number": "CE-004",
                "title": "Owner Requested Electrified Switchable Privacy Glass in Boardroom",
                "status": "Pending",
                "description": (
                    "Owner change from standard tempered glass to PDLC "
                    "switchable smart glass in 18th floor executive boardroom."
                ),
                "grand_total": 24000.0,
            },
            {
                "id": 5,
                "event_number": "CE-005",
                "title": "HVAC Duct Rerouting Clash Resolution per RFI-008",
                "status": "Approved",
                "description": (
                    "Fabrication of offset transitions to split 60x24 duct "
                    "around 8-inch chilled water pipe at Level 6 corridor."
                ),
                "grand_total": 12800.0,
            },
            {
                "id": 6,
                "event_number": "CE-006",
                "title": "Curtain Wall Mullion Reinforcement for Higher Wind Zone Corner",
                "status": "Approved",
                "description": (
                    "Structural steel internal mullion reinforcement sleeves for "
                    "southwest corner curtainwall bays levels 15-20."
                ),
                "grand_total": 65000.0,
            },
            {
                "id": 7,
                "event_number": "CE-007",
                "title": (
                    "Additional Seismic Cable Bracing for Elevator Hoistway Traveling Cables"
                ),
                "status": "Open",
                "description": (
                    "Seismic restraint hardware for high-speed elevator "
                    "traveling cable guides in hoistways 1-3."
                ),
                "grand_total": 28500.0,
            },
            {
                "id": 8,
                "event_number": "CE-008",
                "title": "Substation Primary Feeder Conduit Route Adjustment",
                "status": "Closed",
                "description": (
                    "Reroute Seattle City Light high voltage feeder duct bank to "
                    "avoid perimeter dewatering manifold."
                ),
                "grand_total": 19300.0,
            },
            {
                "id": 9,
                "event_number": "CE-009",
                "title": "Acoustic Insulation Upgrade at Mechanical Penthouse Perimeter",
                "status": "Approved",
                "description": (
                    "Upgrade perimeter walls from single layer gypsum to "
                    "resilient channel with double layer Type X and mass loaded "
                    "vinyl."
                ),
                "grand_total": 15700.0,
            },
            {
                "id": 10,
                "event_number": "CE-010",
                "title": "Stormwater Retention Vault Capacity Expansion per Utility Dept",
                "status": "Approved",
                "description": (
                    "Upsize detention vault volume by 2,500 gallons to satisfy "
                    "revised 100-year storm event municipal criteria."
                ),
                "grand_total": 54200.0,
            },
            {
                "id": 11,
                "event_number": "CE-011",
                "title": "Emergency Generator Fuel Polishing Skid Integration",
                "status": "Pending",
                "description": (
                    "Addition of automated fuel filtration and polishing loop "
                    "for 2,000-gallon belly tank."
                ),
                "grand_total": 22100.0,
            },
        ]

        # Commitments / Subcontracts
        self.commitments: list[dict[str, Any]] = [
            {
                "id": 1,
                "number": "SC-001",
                "title": "Cast-in-Place Concrete Subcontract",
                "vendor_name": "Metro Concrete Solutions",
                "contract_amount": 18500000.0,
                "status": "Approved",
            },
            {
                "id": 2,
                "number": "SC-002",
                "title": "Structural Steel Supply and Erection",
                "vendor_name": "Apex Structural Steel Fabricators",
                "contract_amount": 14600000.0,
                "status": "Approved",
            },
            {
                "id": 3,
                "number": "SC-003",
                "title": "Curtainwall & Architectural Glazing Subcontract",
                "vendor_name": "Pinnacle Glazing & Curtainwall Inc.",
                "contract_amount": 10500000.0,
                "status": "Approved",
            },
            {
                "id": 4,
                "number": "SC-004",
                "title": "HVAC and Mechanical Systems Subcontract",
                "vendor_name": "Helix Mechanical Contractors",
                "contract_amount": 7200000.0,
                "status": "Approved",
            },
            {
                "id": 5,
                "number": "SC-005",
                "title": "Electrical and Low Voltage Systems Subcontract",
                "vendor_name": "Spark Electric Systems",
                "contract_amount": 4500000.0,
                "status": "Approved",
            },
            {
                "id": 6,
                "number": "SC-006",
                "title": "Elevators and Escalators Subcontract",
                "vendor_name": "Otis Elevation Systems",
                "contract_amount": 5800000.0,
                "status": "Approved",
            },
        ]

        # Direct Costs
        self.direct_costs: list[dict[str, Any]] = [
            {
                "id": 1,
                "cost_type": "Equipment",
                "description": "Tower Crane 1 Monthly Lease & Maintenance",
                "amount": 45000.0,
                "status": "Approved",
            },
            {
                "id": 2,
                "cost_type": "Materials",
                "description": "Concrete Cylinder Compressive Strength Break Tests",
                "amount": 12500.0,
                "status": "Approved",
            },
        ]

        # Pay Applications
        self.pay_applications: list[dict[str, Any]] = [
            {
                "id": 1,
                "application_number": "PA-001",
                "period_to": "2026-01-31",
                "status": "Approved",
                "total_completed": 4850000.0,
            },
            {
                "id": 2,
                "application_number": "PA-002",
                "period_to": "2026-02-28",
                "status": "Approved",
                "total_completed": 10250000.0,
            },
        ]

        # Daily logs keyed by date
        self.daily_logs: dict[str, dict[str, Any]] = {
            "2026-03-01": {
                "weather": [
                    {
                        "id": 1,
                        "description": "Overcast with intermittent light rain",
                        "temperature": "48°F",
                    }
                ],
                "notes": [
                    {
                        "id": 1,
                        "comment": (
                            "Level 14 core wall concrete pour completed on schedule. "
                            "Placed 185 CY of 8000 PSI high early mix."
                        ),
                        "status": "Approved",
                    },
                    {
                        "id": 2,
                        "comment": (
                            "City building inspector inspected Level 12 composite "
                            "metal deck shear stud layout. Passed with no "
                            "exceptions."
                        ),
                        "status": "Approved",
                    },
                ],
                "man_hours": [
                    {"id": 1, "company": "Metro Concrete Solutions", "workers": 24, "hours": 192.0},
                    {
                        "id": 2,
                        "company": "Apex Structural Steel Fabricators",
                        "workers": 16,
                        "hours": 128.0,
                    },
                    {
                        "id": 3,
                        "company": "Helix Mechanical Contractors",
                        "workers": 12,
                        "hours": 96.0,
                    },
                    {"id": 4, "company": "Spark Electric Systems", "workers": 10, "hours": 80.0},
                ],
            }
        }

    # Query helpers
    def get_company(self, company_id: int) -> dict[str, Any] | None:
        for c in self.companies:
            if c["id"] == company_id:
                return dict(c)
        return None

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        for p in self.projects:
            if p["id"] == project_id:
                return dict(p)
        return None

    def get_budget(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(b) for b in self.budget_items]

    def get_rfis(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(r) for r in self.rfis]

    def get_rfi(self, project_id: int, rfi_id: int) -> dict[str, Any]:
        for r in self.rfis:
            if r["id"] == rfi_id:
                return dict(r)
        raise KeyError(f"RFI {rfi_id} not found in project {project_id}")

    def create_rfi(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status")
        if (
            isinstance(status, str)
            and normalize_status_string(status) in FORBIDDEN_MUTATION_STATUSES
        ):
            raise SafetyInvariantViolation(
                f"Attempted to create RFI with forbidden terminal status '{status}' in demo mode. "
                "Mutations to terminal/authoritative statuses are blocked by safety guardrails."
            )

        new_id = max((r["id"] for r in self.rfis), default=0) + 1
        new_number = f"RFI-{new_id:03d}"
        new_rfi: dict[str, Any] = {
            "id": new_id,
            "number": payload.get("number", new_number),
            "subject": payload.get("subject", "Untitled RFI Draft"),
            "status": status or "draft",
            "due_date": payload.get("due_date"),
            "ball_in_court": payload.get("ball_in_court") or payload.get("assigned_id"),
            "question": payload.get("question") or payload.get("plain_text_body", ""),
            "responses": [],
        }
        self.rfis.append(new_rfi)
        return dict(new_rfi)

    def get_submittals(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(s) for s in self.submittals]

    def get_submittal(self, project_id: int, submittal_id: int) -> dict[str, Any]:
        for s in self.submittals:
            if s["id"] == submittal_id:
                return dict(s)
        raise KeyError(f"Submittal {submittal_id} not found in project {project_id}")

    def get_change_events(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(ce) for ce in self.change_events]

    def get_change_event(self, project_id: int, ce_id: int) -> dict[str, Any]:
        for ce in self.change_events:
            if ce["id"] == ce_id:
                return dict(ce)
        raise KeyError(f"Change event {ce_id} not found in project {project_id}")

    def get_directory_users(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(u) for u in self.directory_users]

    def get_vendors(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.vendors]

    def get_commitments(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(c) for c in self.commitments]

    def get_commitment(self, project_id: int, commitment_id: int) -> dict[str, Any]:
        for c in self.commitments:
            if c["id"] == commitment_id:
                return dict(c)
        raise KeyError(f"Commitment {commitment_id} not found in project {project_id}")

    def get_cost_codes(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(cc) for cc in self.cost_codes]

    def get_direct_costs(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(dc) for dc in self.direct_costs]

    def get_pay_applications(self, project_id: int) -> list[dict[str, Any]]:
        return [dict(pa) for pa in self.pay_applications]

    def get_daily_logs(self, project_id: int, log_date: str) -> dict[str, Any]:
        if log_date in self.daily_logs:
            return dict(self.daily_logs[log_date])
        return {"weather": [], "notes": [], "man_hours": []}

    def create_daily_log_note(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        log_date = payload.get("log_date", "2026-03-01")
        if log_date not in self.daily_logs:
            self.daily_logs[log_date] = {"weather": [], "notes": [], "man_hours": []}

        notes_list = self.daily_logs[log_date].setdefault("notes", [])
        new_note_id = len(notes_list) + 1
        note_comment = (
            payload.get("comment")
            or payload.get("notes")
            or payload.get("note")
            or payload.get("description", "")
        )
        new_note: dict[str, Any] = {
            "id": new_note_id,
            "comment": note_comment,
            "status": payload.get("status", "draft"),
        }
        notes_list.append(new_note)
        return dict(new_note)

    # In-memory REST API Routing
    def handle_get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Any:
        clean_path = "/" + endpoint.lstrip("/").split("?")[0]
        params = params or {}

        def _paginate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            start = (page - 1) * per_page
            return items[start : start + per_page]

        if clean_path == "/rest/v1.0/companies":
            return _paginate(self.companies)

        if clean_path == "/rest/v1.0/projects":
            return _paginate(self.projects)

        if clean_path == "/rest/v1.0/cost_codes":
            return _paginate(self.cost_codes)

        m_proj_detail = re.match(r"^/rest/v1\.0/projects/(\d+)$", clean_path)
        if m_proj_detail:
            p_id = int(m_proj_detail.group(1))
            proj = self.get_project(p_id)
            return proj if proj is not None else {}

        # /rest/v1.0/projects/{project_id}/...
        m_rfi_detail = re.match(r"^/rest/v1\.0/projects/(\d+)/rfis/(\d+)$", clean_path)
        if m_rfi_detail:
            p_id, r_id = int(m_rfi_detail.group(1)), int(m_rfi_detail.group(2))
            return self.get_rfi(p_id, r_id)

        m_rfis = re.match(r"^/rest/v1\.0/projects/(\d+)/rfis$", clean_path)
        if m_rfis:
            p_id = int(m_rfis.group(1))
            return _paginate(self.get_rfis(p_id))

        m_sub_detail = re.match(r"^/rest/v1\.0/projects/(\d+)/submittals/(\d+)$", clean_path)
        if m_sub_detail:
            p_id, s_id = int(m_sub_detail.group(1)), int(m_sub_detail.group(2))
            return self.get_submittal(p_id, s_id)

        m_submittals = re.match(r"^/rest/v1\.0/projects/(\d+)/submittals$", clean_path)
        if m_submittals:
            p_id = int(m_submittals.group(1))
            return _paginate(self.get_submittals(p_id))

        m_ce_detail = re.match(r"^/rest/v1\.0/projects/(\d+)/change_events/(\d+)$", clean_path)
        if m_ce_detail:
            p_id, c_id = int(m_ce_detail.group(1)), int(m_ce_detail.group(2))
            return self.get_change_event(p_id, c_id)

        m_ces = re.match(r"^/rest/v1\.0/projects/(\d+)/change_events$", clean_path)
        if m_ces:
            p_id = int(m_ces.group(1))
            return _paginate(self.get_change_events(p_id))

        m_com_detail = re.match(r"^/rest/v1\.0/projects/(\d+)/commitments/(\d+)$", clean_path)
        if m_com_detail:
            p_id, c_id = int(m_com_detail.group(1)), int(m_com_detail.group(2))
            return self.get_commitment(p_id, c_id)

        m_commitments = re.match(r"^/rest/v1\.0/projects/(\d+)/commitments$", clean_path)
        if m_commitments:
            p_id = int(m_commitments.group(1))
            return _paginate(self.get_commitments(p_id))

        m_users = re.match(r"^/rest/v1\.0/projects/(\d+)/users$", clean_path)
        if m_users:
            p_id = int(m_users.group(1))
            return _paginate(self.get_directory_users(p_id))

        m_daily_logs = re.match(r"^/rest/v1\.0/projects/(\d+)/daily_logs$", clean_path)
        if m_daily_logs:
            p_id = int(m_daily_logs.group(1))
            log_date = str(params.get("log_date", "2026-03-01"))
            return self.get_daily_logs(p_id, log_date)

        m_budget = re.match(r"^/rest/v1\.0/projects/(\d+)/budget_line_items$", clean_path)
        if m_budget:
            p_id = int(m_budget.group(1))
            return _paginate(self.get_budget(p_id))

        m_direct_costs = re.match(r"^/rest/v1\.0/projects/(\d+)/direct_costs$", clean_path)
        if m_direct_costs:
            p_id = int(m_direct_costs.group(1))
            return _paginate(self.get_direct_costs(p_id))

        m_pay_apps = re.match(r"^/rest/v1\.0/projects/(\d+)/pay_applications$", clean_path)
        if m_pay_apps:
            p_id = int(m_pay_apps.group(1))
            return _paginate(self.get_pay_applications(p_id))

        # Default fallback: return empty list
        return []

    def handle_post(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_path = "/" + endpoint.lstrip("/").split("?")[0]
        payload = json_data or {}

        m_rfis = re.match(r"^/rest/v1\.0/projects/(\d+)/rfis$", clean_path)
        if m_rfis:
            p_id = int(m_rfis.group(1))
            return self.create_rfi(p_id, payload)

        m_daily_logs = re.match(r"^/rest/v1\.0/projects/(\d+)/daily_logs$", clean_path)
        if m_daily_logs:
            p_id = int(m_daily_logs.group(1))
            return self.create_daily_log_note(p_id, payload)

        return {"status": "created", "id": 999}

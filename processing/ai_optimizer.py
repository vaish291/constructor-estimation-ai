"""
Rule-based "AI" cost optimization and material recommendation engine.

Encodes common, well-established construction substitution knowledge
(fly-ash vs red-clay bricks, PPC vs OPC cement, vitrified vs ceramic
tiles, etc.) to suggest lower-cost alternatives and budget-tier material
grades, together with an estimated saving.
"""

# material_name -> (alternative name, cost multiplier vs standard rate, note)
SUBSTITUTIONS = {
    "Bricks": ("Fly Ash Bricks", 0.82, "Lighter, more uniform, ~18% cheaper and reduces mortar consumption."),
    "Cement": ("PPC Cement (Blended)", 0.95, "Marginally cheaper than OPC 53 grade with comparable durability for non-critical RCC."),
    "Tiles": ("Vitrified Tiles (Std Grade)", 0.90, "Lower-cost vitrified alternative to premium ceramic/vitrified tiles with similar finish."),
    "Paint": ("Economy Emulsion Paint", 0.80, "Economy-tier emulsion instead of premium brand, ~20% cheaper for similar coverage."),
    "Steel": ("Fe500D (Optimised Design)", 0.97, "Optimised bar-bending schedule / Fe500D reduces overall steel tonnage slightly."),
}

BUDGET_TIERS = {
    "Economy": {
        "Cement": "PPC / OPC 43 Grade",
        "Steel": "Fe500 (Secondary/Standard Mill)",
        "Tiles": "Ceramic Tiles - Standard Finish",
        "Paint": "Economy Acrylic Emulsion",
        "Doors": "Flush Doors - Laminate Finish",
        "Windows": "Powder Coated Aluminium (Standard)",
    },
    "Standard": {
        "Cement": "OPC 43 / 53 Grade",
        "Steel": "Fe500D (Primary Mill - TMT)",
        "Tiles": "Vitrified Tiles - Glossy Finish",
        "Paint": "Premium Acrylic Emulsion",
        "Doors": "Engineered Wood Flush Doors",
        "Windows": "UPVC Windows",
    },
    "Premium": {
        "Cement": "OPC 53 Grade",
        "Steel": "Fe550D (Primary Mill - TMT)",
        "Tiles": "Large-Format Vitrified / Italian Marble",
        "Paint": "Premium Weatherproof Emulsion / Textured Finish",
        "Doors": "Solid Wood / Designer Doors",
        "Windows": "UPVC / Aluminium Double Glazed Windows",
    },
}


def optimize_costs(material_boq):
    """
    Given a generated material BOQ (list of dicts from generate_ai_boq),
    suggests cheaper equivalent materials and estimates total savings.
    """
    suggestions = []
    total_savings = 0.0

    for item in material_boq:
        name = item["item"]
        if name in SUBSTITUTIONS:
            alt_name, multiplier, note = SUBSTITUTIONS[name]
            current_cost = item["total_cost"]
            optimized_cost = current_cost * multiplier
            saving = current_cost - optimized_cost
            total_savings += saving

            suggestions.append({
                "original_item": name,
                "suggested_alternative": alt_name,
                "current_cost": round(current_cost, 2),
                "optimized_cost": round(optimized_cost, 2),
                "estimated_saving": round(saving, 2),
                "note": note
            })

    return {
        "suggestions": suggestions,
        "total_estimated_saving": round(total_savings, 2)
    }


def recommend_materials(budget_tier="Standard"):
    """Returns recommended material grades/brands for a chosen budget tier."""
    tier = budget_tier if budget_tier in BUDGET_TIERS else "Standard"
    return {
        "budget_tier": tier,
        "recommendations": BUDGET_TIERS[tier]
    }

"""
AI BOQ generation engine.

Thumb Rules for Residential Structural BOQ (per sq.m of built-up area):
- Cement: ~4.3 bags / sq.m
- Steel: ~0.043 Tonnes / sq.m
- Sand: ~0.55 cu.m / sq.m
- Aggregate: ~0.41 cu.m / sq.m
- Bricks: ~80 bricks / sq.m of wall area (height = 3m)

Finishing quantities are derived from the AI-detected geometry:
- Paint: litres = paint_area_sqm / 5 (two coats, ~5 sq.m/litre coverage)
- Tiles: tile_area_sqm directly (floor + wet-area dado)
- Doors / Windows: counted directly from detection
"""

PAINT_COVERAGE_SQM_PER_LITRE = 5.0


def _quantities(built_up_area_sqm, perimeter_m, slab_area_sqm, paint_area_sqm,
                 tile_area_sqm, door_count, window_count):
    wall_area_sqm = perimeter_m * 3.0

    return {
        "Cement": built_up_area_sqm * 4.3,
        "Steel": (built_up_area_sqm * 43.0) / 1000,
        "Sand": built_up_area_sqm * 0.55,
        "Aggregate": built_up_area_sqm * 0.41,
        "Bricks": (wall_area_sqm * 80) / 1000,
        "Paint": paint_area_sqm / PAINT_COVERAGE_SQM_PER_LITRE,
        "Tiles": tile_area_sqm,
        "Doors": float(door_count),
        "Windows": float(window_count),
    }


def generate_ai_boq(built_up_area_sqm, perimeter_m, material_rates, labour_rates,
                     slab_area_sqm=None, paint_area_sqm=None, tile_area_sqm=None,
                     door_count=1, window_count=1,
                     gst_pct=18.0, wastage_pct=None, profit_pct=15.0):
    """
    Generates the full AI-assisted Bill of Quantities including materials,
    labour, slab/paint/tile items, and the GST / wastage / contractor
    profit cost breakdown.

    `wastage_pct`, when provided, overrides each material's own configured
    wastage percentage with a single global value.
    """
    slab_area_sqm = slab_area_sqm if slab_area_sqm is not None else built_up_area_sqm
    paint_area_sqm = paint_area_sqm if paint_area_sqm is not None else perimeter_m * 3.0 * 2
    tile_area_sqm = tile_area_sqm if tile_area_sqm is not None else built_up_area_sqm

    quantities = _quantities(
        built_up_area_sqm, perimeter_m, slab_area_sqm, paint_area_sqm,
        tile_area_sqm, door_count, window_count
    )

    material_boq = []
    total_material_cost = 0.0
    total_wastage_amount = 0.0

    for mat in material_rates:
        name = mat.material_name
        if name in quantities:
            base_qty = quantities[name]
            mat_wastage_pct = wastage_pct if wastage_pct is not None else getattr(mat, 'wastage_pct', 5.0)
            wastage_qty = base_qty * (mat_wastage_pct / 100.0)
            total_qty = base_qty + wastage_qty

            base_cost = base_qty * mat.rate_per_unit
            wastage_cost = wastage_qty * mat.rate_per_unit
            cost = total_qty * mat.rate_per_unit

            total_material_cost += cost
            total_wastage_amount += wastage_cost

            material_boq.append({
                "item": name,
                "base_quantity": round(base_qty, 2),
                "wastage_pct": mat_wastage_pct,
                "quantity": round(total_qty, 2),
                "unit": mat.unit,
                "rate": mat.rate_per_unit,
                "rate_source": getattr(mat, 'rate_source', 'CPWD'),
                "wastage_cost": round(wastage_cost, 2),
                "total_cost": round(cost, 2)
            })

    mason_days = built_up_area_sqm * 1.2
    helper_days = built_up_area_sqm * 2.5
    painter_days = (paint_area_sqm / 15.0)   # ~15 sqm painted per painter/day
    tiler_days = (tile_area_sqm / 8.0)       # ~8 sqm tiled per tiler/day
    carpenter_days = (door_count + window_count) * 0.75

    labour_boq = []
    total_labour_cost = 0.0

    for lab in labour_rates:
        category = lab.category
        days = None
        if "Mason" in category:
            days = mason_days
        elif "Labourer" in category or "Helper" in category:
            days = helper_days
        elif "Painter" in category:
            days = painter_days
        elif "Tile" in category:
            days = tiler_days
        elif "Carpenter" in category:
            days = carpenter_days

        if days is not None:
            cost = days * lab.rate_per_day
            total_labour_cost += cost
            labour_boq.append({
                "category": category,
                "days": round(days, 1),
                "rate": lab.rate_per_day,
                "total_cost": round(cost, 2)
            })

    subtotal = total_material_cost + total_labour_cost
    gst_amount = subtotal * (gst_pct / 100.0)
    profit_amount = subtotal * (profit_pct / 100.0)
    grand_total_ai = subtotal + gst_amount + profit_amount

    return {
        "material_boq": material_boq,
        "labour_boq": labour_boq,
        "material_cost": round(total_material_cost, 2),
        "labour_cost": round(total_labour_cost, 2),
        "wastage_amount": round(total_wastage_amount, 2),
        "gst_pct": gst_pct,
        "gst_amount": round(gst_amount, 2),
        "profit_pct": profit_pct,
        "profit_amount": round(profit_amount, 2),
        "subtotal": round(subtotal, 2),
        "total_ai_cost": round(grand_total_ai, 2),
        "slab_area_sqm": round(slab_area_sqm, 2),
        "paint_area_sqm": round(paint_area_sqm, 2),
        "tile_area_sqm": round(tile_area_sqm, 2),
    }

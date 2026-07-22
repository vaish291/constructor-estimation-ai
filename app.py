import os
import json
import traceback
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash

from config import Config
from database import db, init_db, Location, MaterialRate, LabourRate, Project, CPWD, MPWD
from processing.image_processor import process_floor_plan
from processing.estimator_engine import generate_ai_boq
from processing.ai_optimizer import optimize_costs, recommend_materials, BUDGET_TIERS
from utils.excel_utils import export_boq_to_excel, parse_rates_excel, build_rate_import_template
from utils.pdf_utils import generate_estimate_pdf

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
init_db(app)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route('/')
def dashboard():
    locations = Location.query.all()
    schedules = db.session.query(LabourRate.schedule_type).distinct().all()
    projects = Project.query.order_by(Project.id.desc()).all()
    return render_template(
        'dashboard.html',
        locations=locations,
        schedules=[s[0] for s in schedules],
        projects=projects,
        budget_tiers=list(BUDGET_TIERS.keys()),
        default_gst=Config.DEFAULT_GST_PCT,
        default_wastage=Config.DEFAULT_WASTAGE_PCT,
        default_profit=Config.DEFAULT_PROFIT_PCT,
        using_mysql=Config.using_mysql(),
        active='dashboard',
    )


@app.route('/admin')
def admin_panel():
    materials = MaterialRate.query.all()
    labour = LabourRate.query.all()
    locations = Location.query.all()
    return render_template(
        'admin.html',
        materials=materials,
        labour=labour,
        locations=locations,
        rate_sources=[CPWD, MPWD],
        using_mysql=Config.using_mysql(),
        active='admin',
    )


@app.route('/analytics')
def analytics_page():
    projects = Project.query.order_by(Project.id.asc()).all()
    return render_template('analytics.html', projects=projects, using_mysql=Config.using_mysql(), active='analytics')


# ---------------------------------------------------------------------------
# Admin rate management
# ---------------------------------------------------------------------------

@app.route('/api/add-material', methods=['POST'])
def add_material():
    location_id = int(request.form.get('location_id'))
    material_name = request.form.get('material_name')
    unit = request.form.get('unit')
    rate_per_unit = float(request.form.get('rate_per_unit'))
    rate_source = request.form.get('rate_source', CPWD)
    wastage_pct = float(request.form.get('wastage_pct', 5.0) or 5.0)

    mat = MaterialRate(
        location_id=location_id, material_name=material_name, unit=unit,
        rate_per_unit=rate_per_unit, rate_source=rate_source, wastage_pct=wastage_pct
    )
    db.session.add(mat)
    db.session.commit()
    return redirect(url_for('admin_panel'))


@app.route('/api/add-labour', methods=['POST'])
def add_labour():
    schedule_type = request.form.get('schedule_type')
    category = request.form.get('category')
    rate_per_day = float(request.form.get('rate_per_day'))

    lab = LabourRate(schedule_type=schedule_type, category=category, rate_per_day=rate_per_day)
    db.session.add(lab)
    db.session.commit()
    return redirect(url_for('admin_panel'))


@app.route('/api/rates-template')
def rates_template():
    buf = build_rate_import_template()
    return send_file(
        buf, as_attachment=True, download_name="rate_import_template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route('/api/import-rates', methods=['POST'])
def import_rates():
    if 'rates_file' not in request.files or request.files['rates_file'].filename == '':
        flash("Please choose an Excel (.xlsx) file to import.", "error")
        return redirect(url_for('admin_panel'))

    file = request.files['rates_file']
    try:
        parsed = parse_rates_excel(file.stream)
        added_materials, added_labour = 0, 0

        for m in parsed['materials']:
            db.session.add(MaterialRate(**m))
            added_materials += 1

        for l in parsed['labour']:
            db.session.add(LabourRate(**l))
            added_labour += 1

        db.session.commit()
        flash(f"Imported {added_materials} material rate(s) and {added_labour} labour rate(s).", "success")
    except Exception as e:
        flash(f"Failed to import rates: {str(e)}", "error")

    return redirect(url_for('admin_panel'))


# ---------------------------------------------------------------------------
# AI Floor Plan Analysis + BOQ generation
# ---------------------------------------------------------------------------

@app.route('/api/analyze-plan', methods=['POST'])
def analyze_plan():
    if 'plan_file' not in request.files:
        return jsonify({"error": "No plan file uploaded"}), 400

    file = request.files['plan_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        scale_factor = float(request.form.get('scale_factor', 50.0))
        location_id = int(request.form.get('location_id', 1))
        schedule_type = request.form.get('schedule_type', CPWD)
        gst_pct = float(request.form.get('gst_pct', Config.DEFAULT_GST_PCT))
        wastage_override = request.form.get('wastage_pct')
        wastage_pct = float(wastage_override) if wastage_override not in (None, '', 'auto') else None
        profit_pct = float(request.form.get('profit_pct', Config.DEFAULT_PROFIT_PCT))
        budget_tier = request.form.get('budget_tier', 'Standard')

        plan_metrics = process_floor_plan(filepath, pixels_per_meter=scale_factor)

        mat_rates = MaterialRate.query.filter_by(location_id=location_id).all()
        lab_rates = LabourRate.query.filter_by(schedule_type=schedule_type).all()

        boq_results = generate_ai_boq(
            plan_metrics['built_up_area_sqm'], plan_metrics['perimeter_m'],
            mat_rates, lab_rates,
            slab_area_sqm=plan_metrics['slab_area_sqm'],
            paint_area_sqm=plan_metrics['paint_area_sqm'],
            tile_area_sqm=plan_metrics['tile_area_sqm'],
            door_count=plan_metrics['door_count'],
            window_count=plan_metrics['window_count'],
            gst_pct=gst_pct, wastage_pct=wastage_pct, profit_pct=profit_pct
        )

        optimization = optimize_costs(boq_results['material_boq'])
        recommendation = recommend_materials(budget_tier)

        return jsonify({
            "metrics": plan_metrics,
            "boq": boq_results,
            "optimization": optimization,
            "recommendation": recommendation,
            "rate_source": schedule_type,
            "location_id": location_id,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Failed to analyze floor plan: {str(e)}"}), 500


@app.route('/api/recommend-materials')
def api_recommend_materials():
    budget_tier = request.args.get('budget_tier', 'Standard')
    return jsonify(recommend_materials(budget_tier))


# ---------------------------------------------------------------------------
# Save / compare / export
# ---------------------------------------------------------------------------

@app.route('/api/save-comparison', methods=['POST'])
def save_comparison():
    data = request.json or {}
    name = data.get('project_name', 'Untitled Project')
    area = data.get('area', 0.0)
    perimeter = data.get('perimeter', 0.0)
    ai_cost = data.get('ai_cost', 0.0)
    manual_cost = data.get('manual_cost', 0.0)

    variance = round(((ai_cost - manual_cost) / manual_cost) * 100, 2) if manual_cost > 0 else 0.0

    boq = data.get('boq', {}) or {}
    metrics = data.get('metrics', {}) or {}

    project = Project(
        name=name,
        built_up_area_sqm=area,
        perimeter_m=perimeter,
        room_count=metrics.get('room_count', 0),
        wall_count=metrics.get('wall_count', 0),
        door_count=metrics.get('door_count', 0),
        window_count=metrics.get('window_count', 0),
        slab_area_sqm=boq.get('slab_area_sqm', 0.0),
        paint_area_sqm=boq.get('paint_area_sqm', 0.0),
        tile_area_sqm=boq.get('tile_area_sqm', 0.0),
        material_cost=boq.get('material_cost', 0.0),
        labour_cost=boq.get('labour_cost', 0.0),
        wastage_amount=boq.get('wastage_amount', 0.0),
        gst_amount=boq.get('gst_amount', 0.0),
        profit_amount=boq.get('profit_amount', 0.0),
        optimized_cost=data.get('optimized_total', 0.0),
        ai_total_cost=ai_cost,
        manual_total_cost=manual_cost,
        variance_pct=variance,
        rate_source=data.get('rate_source', CPWD),
        location_id=data.get('location_id'),
        boq_json=json.dumps({"metrics": metrics, "boq": boq, "optimization": data.get('optimization', {})}),
    )
    db.session.add(project)
    db.session.commit()

    return jsonify({"success": True, "project_id": project.id, "variance": variance})


def _load_project_payload(project):
    metrics, boq, optimization = {}, {}, {}
    if project.boq_json:
        try:
            payload = json.loads(project.boq_json)
            metrics = payload.get('metrics', {})
            boq = payload.get('boq', {})
            optimization = payload.get('optimization', {})
        except Exception:
            pass
    return metrics, boq, optimization


@app.route('/api/export-pdf/<int:project_id>')
def export_pdf(project_id):
    project = Project.query.get_or_404(project_id)
    metrics, boq, optimization = _load_project_payload(project)

    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"Report_Project_{project.id}.pdf")
    generate_estimate_pdf(pdf_path, project, metrics=metrics, boq=boq, optimization=optimization)
    return send_file(pdf_path, as_attachment=True)


@app.route('/api/export-excel/<int:project_id>')
def export_excel(project_id):
    project = Project.query.get_or_404(project_id)
    metrics, boq, optimization = _load_project_payload(project)

    if not boq:
        # Fall back to persisted summary fields if the full BOQ wasn't stored.
        boq = {
            "material_boq": [], "labour_boq": [],
            "material_cost": project.material_cost, "labour_cost": project.labour_cost,
            "wastage_amount": project.wastage_amount, "gst_amount": project.gst_amount,
            "gst_pct": 18.0, "profit_amount": project.profit_amount, "profit_pct": 15.0,
            "total_ai_cost": project.ai_total_cost,
            "slab_area_sqm": project.slab_area_sqm, "paint_area_sqm": project.paint_area_sqm,
            "tile_area_sqm": project.tile_area_sqm,
        }
    if not metrics:
        metrics = {
            "built_up_area_sqm": project.built_up_area_sqm, "perimeter_m": project.perimeter_m,
            "room_count": project.room_count, "wall_count": project.wall_count,
            "door_count": project.door_count, "window_count": project.window_count,
        }

    buf = export_boq_to_excel(project.name, metrics, boq, optimization)
    return send_file(
        buf, as_attachment=True, download_name=f"BOQ_{project.name.replace(' ', '_')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ---------------------------------------------------------------------------
# Analytics dashboard data
# ---------------------------------------------------------------------------

@app.route('/api/analytics-data')
def analytics_data():
    projects = Project.query.order_by(Project.id.asc()).all()

    labels = [p.name for p in projects]
    ai_costs = [p.ai_total_cost or 0 for p in projects]
    manual_costs = [p.manual_total_cost or 0 for p in projects]
    variances = [p.variance_pct or 0 for p in projects]
    areas = [p.built_up_area_sqm or 0 for p in projects]

    total_projects = len(projects)
    total_ai_value = sum(ai_costs)
    avg_cost_per_sqm = (sum(ai_costs) / sum(areas)) if sum(areas) > 0 else 0
    avg_variance = (sum(variances) / total_projects) if total_projects > 0 else 0

    # Cost breakdown of latest project
    breakdown = {"material": 0, "labour": 0, "wastage": 0, "gst": 0, "profit": 0}
    if projects:
        latest = projects[-1]
        breakdown = {
            "material": latest.material_cost or 0,
            "labour": latest.labour_cost or 0,
            "wastage": latest.wastage_amount or 0,
            "gst": latest.gst_amount or 0,
            "profit": latest.profit_amount or 0,
        }

    return jsonify({
        "labels": labels,
        "ai_costs": ai_costs,
        "manual_costs": manual_costs,
        "variances": variances,
        "areas": areas,
        "summary": {
            "total_projects": total_projects,
            "total_ai_value": round(total_ai_value, 2),
            "avg_cost_per_sqm": round(avg_cost_per_sqm, 2),
            "avg_variance": round(avg_variance, 2),
        },
        "latest_breakdown": breakdown,
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)

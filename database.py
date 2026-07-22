from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

CPWD = "Central (CPWD)"
MPWD = "Maharashtra PWD"


class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)

    material_rates = db.relationship('MaterialRate', backref='location', lazy=True)


class MaterialRate(db.Model):
    __tablename__ = 'material_rates'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    material_name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    rate_per_unit = db.Column(db.Float, nullable=False)
    # Which official schedule this rate is benchmarked against.
    rate_source = db.Column(db.String(50), nullable=False, default=CPWD)
    # Default wastage percentage applied to this material during BOQ generation.
    wastage_pct = db.Column(db.Float, nullable=False, default=5.0)


class LabourRate(db.Model):
    __tablename__ = 'labour_rates'
    id = db.Column(db.Integer, primary_key=True)
    schedule_type = db.Column(db.String(50), nullable=False)  # Central (CPWD), Maharashtra PWD, State, District
    district = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=False)      # Mason, Carpenter, Labourer
    rate_per_day = db.Column(db.Float, nullable=False)


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    perimeter_m = db.Column(db.Float, default=0.0)
    built_up_area_sqm = db.Column(db.Float, default=0.0)

    # AI Floor plan detection results
    room_count = db.Column(db.Integer, default=0)
    wall_count = db.Column(db.Integer, default=0)
    door_count = db.Column(db.Integer, default=0)
    window_count = db.Column(db.Integer, default=0)

    # Area calculations
    slab_area_sqm = db.Column(db.Float, default=0.0)
    paint_area_sqm = db.Column(db.Float, default=0.0)
    tile_area_sqm = db.Column(db.Float, default=0.0)

    # Cost breakdown
    material_cost = db.Column(db.Float, default=0.0)
    labour_cost = db.Column(db.Float, default=0.0)
    wastage_amount = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, default=0.0)
    profit_amount = db.Column(db.Float, default=0.0)
    optimized_cost = db.Column(db.Float, default=0.0)

    ai_total_cost = db.Column(db.Float, default=0.0)
    manual_total_cost = db.Column(db.Float, default=0.0)
    variance_pct = db.Column(db.Float, default=0.0)

    rate_source = db.Column(db.String(50), default=CPWD)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    # Full BOQ / detection payload stored as JSON text so PDF/Excel exports
    # and the analytics dashboard can be regenerated later without re-upload.
    boq_json = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())


def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _run_light_migrations()
        seed_initial_data()


def _run_light_migrations():
    """Add newly-introduced columns to pre-existing SQLite/MySQL databases
    created by earlier versions of this app, without requiring a full
    migration framework."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    try:
        existing_tables = inspector.get_table_names()
    except Exception:
        return

    migrations = {
        'material_rates': [
            ("rate_source", "VARCHAR(50) DEFAULT 'Central (CPWD)'"),
            ("wastage_pct", "FLOAT DEFAULT 5.0"),
        ],
        'projects': [
            ("room_count", "INTEGER DEFAULT 0"),
            ("wall_count", "INTEGER DEFAULT 0"),
            ("door_count", "INTEGER DEFAULT 0"),
            ("window_count", "INTEGER DEFAULT 0"),
            ("slab_area_sqm", "FLOAT DEFAULT 0.0"),
            ("paint_area_sqm", "FLOAT DEFAULT 0.0"),
            ("tile_area_sqm", "FLOAT DEFAULT 0.0"),
            ("material_cost", "FLOAT DEFAULT 0.0"),
            ("labour_cost", "FLOAT DEFAULT 0.0"),
            ("wastage_amount", "FLOAT DEFAULT 0.0"),
            ("gst_amount", "FLOAT DEFAULT 0.0"),
            ("profit_amount", "FLOAT DEFAULT 0.0"),
            ("optimized_cost", "FLOAT DEFAULT 0.0"),
            ("rate_source", "VARCHAR(50) DEFAULT 'Central (CPWD)'"),
            ("location_id", "INTEGER"),
            ("boq_json", "TEXT"),
        ],
    }

    for table, columns in migrations.items():
        if table not in existing_tables:
            continue
        existing_cols = {c['name'] for c in inspector.get_columns(table)}
        for col_name, col_def in columns:
            if col_name not in existing_cols:
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
                except Exception:
                    pass


def seed_initial_data():
    if Location.query.first() is None:
        loc1 = Location(state="Maharashtra", district="Nashik", city="Nashik City")
        loc2 = Location(state="Maharashtra", district="Mumbai", city="Mumbai Suburban")
        loc3 = Location(state="Maharashtra", district="Pune", city="Pune City")
        db.session.add_all([loc1, loc2, loc3])
        db.session.commit()

        # Seed default Material Rates (CPWD benchmarked, Nashik)
        materials = [
            MaterialRate(location_id=loc1.id, material_name="Cement", unit="Bag", rate_per_unit=380.0, rate_source=CPWD, wastage_pct=3.0),
            MaterialRate(location_id=loc1.id, material_name="Steel", unit="Tonne", rate_per_unit=62000.0, rate_source=CPWD, wastage_pct=2.0),
            MaterialRate(location_id=loc1.id, material_name="Sand", unit="Cu.m", rate_per_unit=1400.0, rate_source=CPWD, wastage_pct=10.0),
            MaterialRate(location_id=loc1.id, material_name="Aggregate", unit="Cu.m", rate_per_unit=1100.0, rate_source=CPWD, wastage_pct=8.0),
            MaterialRate(location_id=loc1.id, material_name="Bricks", unit="1000 Pcs", rate_per_unit=7500.0, rate_source=CPWD, wastage_pct=5.0),
            MaterialRate(location_id=loc1.id, material_name="Paint", unit="Litre", rate_per_unit=280.0, rate_source=CPWD, wastage_pct=5.0),
            MaterialRate(location_id=loc1.id, material_name="Tiles", unit="Sq.m", rate_per_unit=650.0, rate_source=CPWD, wastage_pct=8.0),
            MaterialRate(location_id=loc1.id, material_name="Doors", unit="Nos", rate_per_unit=6500.0, rate_source=CPWD, wastage_pct=0.0),
            MaterialRate(location_id=loc1.id, material_name="Windows", unit="Nos", rate_per_unit=4500.0, rate_source=CPWD, wastage_pct=0.0),
            # Mumbai (Maharashtra PWD benchmarked)
            MaterialRate(location_id=loc2.id, material_name="Cement", unit="Bag", rate_per_unit=410.0, rate_source=MPWD, wastage_pct=3.0),
            MaterialRate(location_id=loc2.id, material_name="Steel", unit="Tonne", rate_per_unit=64500.0, rate_source=MPWD, wastage_pct=2.0),
            MaterialRate(location_id=loc2.id, material_name="Sand", unit="Cu.m", rate_per_unit=1650.0, rate_source=MPWD, wastage_pct=10.0),
            MaterialRate(location_id=loc2.id, material_name="Aggregate", unit="Cu.m", rate_per_unit=1250.0, rate_source=MPWD, wastage_pct=8.0),
            MaterialRate(location_id=loc2.id, material_name="Bricks", unit="1000 Pcs", rate_per_unit=8200.0, rate_source=MPWD, wastage_pct=5.0),
            MaterialRate(location_id=loc2.id, material_name="Paint", unit="Litre", rate_per_unit=310.0, rate_source=MPWD, wastage_pct=5.0),
            MaterialRate(location_id=loc2.id, material_name="Tiles", unit="Sq.m", rate_per_unit=750.0, rate_source=MPWD, wastage_pct=8.0),
            MaterialRate(location_id=loc2.id, material_name="Doors", unit="Nos", rate_per_unit=7200.0, rate_source=MPWD, wastage_pct=0.0),
            MaterialRate(location_id=loc2.id, material_name="Windows", unit="Nos", rate_per_unit=5000.0, rate_source=MPWD, wastage_pct=0.0),
            # Pune (Maharashtra PWD benchmarked)
            MaterialRate(location_id=loc3.id, material_name="Cement", unit="Bag", rate_per_unit=395.0, rate_source=MPWD, wastage_pct=3.0),
            MaterialRate(location_id=loc3.id, material_name="Steel", unit="Tonne", rate_per_unit=63200.0, rate_source=MPWD, wastage_pct=2.0),
            MaterialRate(location_id=loc3.id, material_name="Sand", unit="Cu.m", rate_per_unit=1500.0, rate_source=MPWD, wastage_pct=10.0),
            MaterialRate(location_id=loc3.id, material_name="Aggregate", unit="Cu.m", rate_per_unit=1150.0, rate_source=MPWD, wastage_pct=8.0),
            MaterialRate(location_id=loc3.id, material_name="Bricks", unit="1000 Pcs", rate_per_unit=7900.0, rate_source=MPWD, wastage_pct=5.0),
            MaterialRate(location_id=loc3.id, material_name="Paint", unit="Litre", rate_per_unit=295.0, rate_source=MPWD, wastage_pct=5.0),
            MaterialRate(location_id=loc3.id, material_name="Tiles", unit="Sq.m", rate_per_unit=700.0, rate_source=MPWD, wastage_pct=8.0),
            MaterialRate(location_id=loc3.id, material_name="Doors", unit="Nos", rate_per_unit=6800.0, rate_source=MPWD, wastage_pct=0.0),
            MaterialRate(location_id=loc3.id, material_name="Windows", unit="Nos", rate_per_unit=4700.0, rate_source=MPWD, wastage_pct=0.0),
        ]

        # Seed default Labour Rates (CPWD + Maharashtra PWD schedules)
        labour = [
            LabourRate(schedule_type=CPWD, category="Mason", rate_per_day=850.0),
            LabourRate(schedule_type=CPWD, category="Helper/Labourer", rate_per_day=550.0),
            LabourRate(schedule_type=CPWD, category="Carpenter", rate_per_day=900.0),
            LabourRate(schedule_type=CPWD, category="Painter", rate_per_day=800.0),
            LabourRate(schedule_type=CPWD, category="Tile Setter", rate_per_day=870.0),
            LabourRate(schedule_type=MPWD, category="Mason", rate_per_day=800.0),
            LabourRate(schedule_type=MPWD, category="Helper/Labourer", rate_per_day=520.0),
            LabourRate(schedule_type=MPWD, category="Carpenter", rate_per_day=860.0),
            LabourRate(schedule_type=MPWD, category="Painter", rate_per_day=760.0),
            LabourRate(schedule_type=MPWD, category="Tile Setter", rate_per_day=820.0),
            LabourRate(schedule_type="State Schedule", category="Mason", rate_per_day=780.0),
            LabourRate(schedule_type="State Schedule", category="Helper/Labourer", rate_per_day=500.0),
            LabourRate(schedule_type="District Schedule", category="Mason", rate_per_day=720.0),
            LabourRate(schedule_type="District Schedule", category="Helper/Labourer", rate_per_day=450.0),
        ]

        db.session.add_all(materials + labour)
        db.session.commit()

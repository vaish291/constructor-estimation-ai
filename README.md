# BuildAI Construction Estimator

Production-ready Flask application for AI-assisted floor plan analysis,
automated Bill of Quantities (BOQ) generation, CPWD / Maharashtra PWD rate
benchmarking, GST/wastage/contractor-profit costing, AI cost optimization,
Excel import/export, professional PDF reporting, and an analytics dashboard.

## Features

- **MySQL-ready database** (SQLAlchemy) with automatic SQLite fallback for local dev
- **AI Floor Plan Analysis** — OpenCV + OCR (Tesseract) powered
- **Room, Wall, Door & Window Detection** from uploaded PDF/image plans
- **Slab, Paint & Tile Area Calculation** derived from detected geometry
- **AI BOQ Generation** — materials, labour, slab/paint/tile/doors/windows
- **Material & Labour Cost Estimation**
- **CPWD & Maharashtra PWD Rate schedules** (plus State/District)
- **GST, Wastage & Contractor Profit** — configurable, itemised in every estimate
- **AI Cost Optimization** — suggests cheaper equivalent materials with estimated savings
- **AI Material Recommendation** — Economy / Standard / Premium tier grade suggestions
- **Excel Import/Export** — bulk rate import + full BOQ export (openpyxl)
- **Professional PDF Estimate Report** (ReportLab, multi-section)
- **Analytics Dashboard** (Chart.js) — cost breakdowns, trends, variance
- **Modern responsive Bootstrap 5 UI**

## Quick Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   Tesseract OCR must also be installed on the system (`sudo apt install tesseract-ocr`
   on Debian/Ubuntu) for the AI floor-plan OCR feature.

2. **Configure the database (optional)**

   By default the app runs on a local SQLite file (`construction.db`) so it
   works out-of-the-box. To use MySQL, set these environment variables
   before starting the app:

   ```bash
   export MYSQL_HOST=localhost
   export MYSQL_PORT=3306
   export MYSQL_USER=root
   export MYSQL_PASSWORD=yourpassword
   export MYSQL_DB=construction_estimator
   ```

   Create the database first: `CREATE DATABASE construction_estimator;`
   Tables and seed data are created automatically on first run.

3. **Run the Application**
   ```bash
   python app.py
   ```

4. **Open in Browser**
   Go to [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Pages

- `/` — Estimator dashboard: upload a plan, configure GST/wastage/profit,
  view AI detection results, BOQ, cost optimization and material
  recommendations, then compare against a manual estimate.
- `/admin` — Rate Schedule Admin: manage material/labour rates (CPWD /
  Maharashtra PWD), bulk import/export rates via Excel.
- `/analytics` — Analytics dashboard with Chart.js visualizations across
  all saved projects.

## Notes on AI Detection

Room/wall/door/window detection uses OpenCV contour analysis, Hough line
transforms and convexity-defect gap detection on the binarized floor plan
— a heuristic computer-vision approach rather than a trained deep-learning
model. It works best on plans with clear, dark wall lines; results should
be verified for critical estimates.

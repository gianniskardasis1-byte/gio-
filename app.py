"""AeroNetB Aerospace Supply Chain Management – Web Dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from flask import Flask, render_template, request

app = Flask(__name__)


@app.context_processor
def inject_now() -> dict:
    return {"now": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

# ──────────────────────── Sample / mock data ────────────────────────

SUPPLIERS = [
    {
        "id": "SUP-001",
        "name": "TitanForge GmbH",
        "country": "Germany",
        "email": "procurement@titanforge.de",
        "phone": "+49-89-5550001",
        "accreditation": "AS9100D",
        "status": "Approved",
        "on_time_pct": 96,
        "defect_rate": 0.8,
    },
    {
        "id": "SUP-002",
        "name": "SkyMet Composites",
        "country": "France",
        "email": "supply@skymet.fr",
        "phone": "+33-1-4000002",
        "accreditation": "NADCAP",
        "status": "Approved",
        "on_time_pct": 91,
        "defect_rate": 1.4,
    },
    {
        "id": "SUP-003",
        "name": "Aegean Precision Ltd",
        "country": "Greece",
        "email": "sales@aegeanprecision.gr",
        "phone": "+30-210-5000003",
        "accreditation": "ISO9001",
        "status": "Under Review",
        "on_time_pct": 78,
        "defect_rate": 3.2,
    },
    {
        "id": "SUP-004",
        "name": "AlphaAlloys S.A.",
        "country": "Spain",
        "email": "info@alphaalloys.es",
        "phone": "+34-91-5000004",
        "accreditation": "AS9100D",
        "status": "Approved",
        "on_time_pct": 89,
        "defect_rate": 2.1,
    },
]

ORDERS = [
    {
        "id": "PO-2026-0001",
        "supplier": "TitanForge GmbH",
        "part": "Fuselage Panel A320",
        "quantity": 20,
        "amount": 142000,
        "currency": "EUR",
        "order_date": "2026-02-15",
        "delivery_date": "2026-03-18",
        "status": "In Transit",
        "status_class": "in-transit",
    },
    {
        "id": "PO-2026-0002",
        "supplier": "SkyMet Composites",
        "part": "Wing Rib Composite",
        "quantity": 50,
        "amount": 87500,
        "currency": "EUR",
        "order_date": "2026-02-20",
        "delivery_date": "2026-03-25",
        "status": "Pending",
        "status_class": "pending",
    },
    {
        "id": "PO-2026-0003",
        "supplier": "AlphaAlloys S.A.",
        "part": "Titanium Fastener Set",
        "quantity": 2000,
        "amount": 34800,
        "currency": "EUR",
        "order_date": "2026-03-01",
        "delivery_date": "2026-03-20",
        "status": "Delivered",
        "status_class": "delivered",
    },
    {
        "id": "PO-2026-0004",
        "supplier": "Aegean Precision Ltd",
        "part": "Hydraulic Bracket B737",
        "quantity": 10,
        "amount": 51000,
        "currency": "EUR",
        "order_date": "2026-03-05",
        "delivery_date": "2026-04-01",
        "status": "Pending",
        "status_class": "pending",
    },
]

SHIPMENTS = [
    {
        "id": "SHIP-0001",
        "order_id": "PO-2026-0001",
        "tracking": "TRK-AX-445577",
        "carrier": "BlueSky Logistics",
        "origin": "Hamburg, DE",
        "destination": "Athens, GR",
        "status": "In Transit",
        "status_class": "in-transit",
        "eta": "2026-03-18",
        "last_location": "Aegean Sea Corridor",
        "temperature": 18.4,
        "vibration": 1.12,
        "pressure": 101.2,
        "shock": False,
    },
    {
        "id": "SHIP-0002",
        "order_id": "PO-2026-0003",
        "tracking": "TRK-BX-112233",
        "carrier": "EuroExpress Cargo",
        "origin": "Madrid, ES",
        "destination": "Athens, GR",
        "status": "Delivered",
        "status_class": "delivered",
        "eta": "2026-03-09",
        "last_location": "Athens Hub",
        "temperature": 21.0,
        "vibration": 0.55,
        "pressure": 100.8,
        "shock": False,
    },
    {
        "id": "SHIP-0003",
        "order_id": "PO-2026-0002",
        "tracking": "TRK-CX-998877",
        "carrier": "AeroFreight SA",
        "origin": "Toulouse, FR",
        "destination": "Athens, GR",
        "status": "Pending",
        "status_class": "pending",
        "eta": "2026-03-25",
        "last_location": "Toulouse Warehouse",
        "temperature": None,
        "vibration": None,
        "pressure": None,
        "shock": None,
    },
]

QC_REPORTS = [
    {
        "id": "QCR-2026-1001",
        "order_id": "PO-2026-0001",
        "part": "Fuselage Panel A320",
        "supplier": "TitanForge GmbH",
        "type": "COMBINED",
        "status": "Submitted",
        "status_class": "submitted",
        "inspector": "E. Papadopoulos",
        "created": "2026-03-03",
        "result": "PASS",
        "result_class": "pass",
    },
    {
        "id": "QCR-2026-1002",
        "order_id": "PO-2026-0003",
        "part": "Titanium Fastener Set",
        "supplier": "AlphaAlloys S.A.",
        "type": "DIMENSIONAL",
        "status": "Approved",
        "status_class": "approved",
        "inspector": "K. Stavros",
        "created": "2026-03-08",
        "result": "PASS",
        "result_class": "pass",
    },
    {
        "id": "QCR-2026-1003",
        "order_id": "PO-2026-0004",
        "part": "Hydraulic Bracket B737",
        "supplier": "Aegean Precision Ltd",
        "type": "NDT",
        "status": "Draft",
        "status_class": "draft",
        "inspector": "E. Papadopoulos",
        "created": "2026-03-09",
        "result": "PENDING",
        "result_class": "pending",
    },
]

CERTIFICATIONS = [
    {
        "id": "CERT-2026-9001",
        "report_id": "QCR-2026-1001",
        "part": "Fuselage Panel A320",
        "supplier": "TitanForge GmbH",
        "inspector": "E. Papadopoulos",
        "status": "Approved",
        "status_class": "approved",
        "immutable": True,
        "finalized": "2026-03-03",
        "batch": "BATCH-TI-33881",
        "origin": "Germany",
    },
    {
        "id": "CERT-2026-9002",
        "report_id": "QCR-2026-1002",
        "part": "Titanium Fastener Set",
        "supplier": "AlphaAlloys S.A.",
        "inspector": "K. Stavros",
        "status": "Approved",
        "status_class": "approved",
        "immutable": True,
        "finalized": "2026-03-08",
        "batch": "BATCH-AL-77221",
        "origin": "Spain",
    },
    {
        "id": "CERT-2026-9003",
        "report_id": "QCR-2026-1003",
        "part": "Hydraulic Bracket B737",
        "supplier": "Aegean Precision Ltd",
        "inspector": "E. Papadopoulos",
        "status": "Draft",
        "status_class": "draft",
        "immutable": False,
        "finalized": None,
        "batch": "BATCH-SS-44109",
        "origin": "Greece",
    },
]

IOT_DEVICES = [
    {
        "id": "DEV-TEMP-01",
        "type": "TEMPERATURE",
        "target": "CNC Machine EQ-CNC-01",
        "facility": "Athens Facility",
        "value": 52.3,
        "unit": "°C",
        "threshold_min": 5,
        "threshold_max": 70,
        "anomaly": False,
        "status_class": "ok",
        "last_reading": "2026-03-10 14:00",
    },
    {
        "id": "DEV-VIB-02",
        "type": "VIBRATION",
        "target": "Lathe Machine EQ-LT-02",
        "facility": "Athens Facility",
        "value": 4.8,
        "unit": "mm/s",
        "threshold_min": 0,
        "threshold_max": 4.5,
        "anomaly": True,
        "status_class": "warning",
        "last_reading": "2026-03-10 13:55",
    },
    {
        "id": "DEV-GPS-01",
        "type": "GPS",
        "target": "Shipment SHIP-0001",
        "facility": "In Transit",
        "value": None,
        "unit": "deg",
        "threshold_min": None,
        "threshold_max": None,
        "anomaly": False,
        "status_class": "ok",
        "last_reading": "2026-03-10 14:00",
    },
    {
        "id": "DEV-PRES-03",
        "type": "PRESSURE",
        "target": "Storage Tank EQ-ST-03",
        "facility": "Thessaloniki Facility",
        "value": 112.7,
        "unit": "kPa",
        "threshold_min": 95,
        "threshold_max": 115,
        "anomaly": False,
        "status_class": "ok",
        "last_reading": "2026-03-10 13:50",
    },
]

AUDIT_LOGS = [
    {
        "id": "AUD-20260310-0005",
        "time": "2026-03-10 14:05",
        "emp_id": "E1001",
        "employee": "A. Nikolaou",
        "role": "Procurement",
        "action": "INSERT",
        "entity": "purchase_order",
        "entity_key": "PO-2026-0004",
        "outcome": "SUCCESS",
        "source_ip": "10.0.0.25",
    },
    {
        "id": "AUD-20260310-0004",
        "time": "2026-03-10 13:30",
        "emp_id": "E2001",
        "employee": "E. Papadopoulos",
        "role": "Inspector",
        "action": "APPROVE",
        "entity": "qc_report",
        "entity_key": "QCR-2026-1002",
        "outcome": "SUCCESS",
        "source_ip": "10.0.0.31",
    },
    {
        "id": "AUD-20260310-0003",
        "time": "2026-03-10 12:15",
        "emp_id": "E3001",
        "employee": "M. Kostas",
        "role": "Manager",
        "action": "VIEW",
        "entity": "shipment",
        "entity_key": "SHIP-0001",
        "outcome": "SUCCESS",
        "source_ip": "10.0.0.40",
    },
    {
        "id": "AUD-20260310-0002",
        "time": "2026-03-10 11:45",
        "emp_id": "E4001",
        "employee": "P. Alexis",
        "role": "Engineer",
        "action": "VIEW",
        "entity": "iot_device",
        "entity_key": "DEV-VIB-02",
        "outcome": "SUCCESS",
        "source_ip": "10.0.0.55",
    },
    {
        "id": "AUD-20260310-0001",
        "time": "2026-03-09 16:00",
        "emp_id": "E2001",
        "employee": "E. Papadopoulos",
        "role": "Inspector",
        "action": "INSERT",
        "entity": "component_certification",
        "entity_key": "CERT-2026-9002",
        "outcome": "SUCCESS",
        "source_ip": "10.0.0.31",
    },
]


def kpi_summary() -> dict:
    return {
        "total_orders": len(ORDERS),
        "active_shipments": sum(1 for s in SHIPMENTS if s["status"] == "In Transit"),
        "pending_qc": sum(1 for r in QC_REPORTS if r["status"] in ("Draft", "Submitted")),
        "iot_alerts": sum(1 for d in IOT_DEVICES if d["anomaly"]),
        "approved_suppliers": sum(1 for s in SUPPLIERS if s["status"] == "Approved"),
        "total_certifications": len(CERTIFICATIONS),
    }


# ──────────────────────────── Routes ────────────────────────────────

@app.route("/")
def index():
    kpi = kpi_summary()
    return render_template("index.html", kpi=kpi, orders=ORDERS[:4],
                           shipments=SHIPMENTS, iot_devices=IOT_DEVICES)


@app.route("/suppliers")
def suppliers():
    query = request.args.get("q", "").lower()
    filtered = [s for s in SUPPLIERS if query in s["name"].lower() or
                query in s["country"].lower() or query in s["id"].lower()] if query else SUPPLIERS
    return render_template("suppliers.html", suppliers=filtered, query=query)


@app.route("/orders")
def orders():
    status_filter = request.args.get("status", "")
    filtered = [o for o in ORDERS if o["status"] == status_filter] if status_filter else ORDERS
    statuses = sorted({o["status"] for o in ORDERS})
    return render_template("orders.html", orders=filtered, statuses=statuses,
                           status_filter=status_filter)


@app.route("/shipments")
def shipments():
    return render_template("shipments.html", shipments=SHIPMENTS)


@app.route("/qc")
def qc():
    result_filter = request.args.get("result", "")
    filtered = [r for r in QC_REPORTS if r["result"] == result_filter] if result_filter else QC_REPORTS
    results = sorted({r["result"] for r in QC_REPORTS})
    return render_template("qc.html", reports=filtered, results=results,
                           result_filter=result_filter)


@app.route("/certifications")
def certifications():
    return render_template("certifications.html", certifications=CERTIFICATIONS)


@app.route("/iot")
def iot():
    alerts = [d for d in IOT_DEVICES if d["anomaly"]]
    return render_template("iot.html", devices=IOT_DEVICES, alerts=alerts)


@app.route("/audit")
def audit():
    emp_filter = request.args.get("emp", "")
    filtered = [a for a in AUDIT_LOGS if emp_filter.lower() in a["emp_id"].lower() or
                emp_filter.lower() in a["employee"].lower()] if emp_filter else AUDIT_LOGS
    return render_template("audit.html", logs=filtered, emp_filter=emp_filter)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

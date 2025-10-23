import math
from decimal import Decimal
from datetime import datetime
from flask import Flask, request, jsonify
from sqlalchemy import func
from models import db, User, Zone, Vehicle, ParkingSession
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///parkilite.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
with app.app_context():
    db.create_all()
    demo = User.query.filter_by(email="demo@iberopuebla.mx").first()
    if not demo:
        demo = User(username="demo", email="demo@iberopuebla.mx", balance=Decimal("300.00"))
        db.session.add(demo)
        db.session.commit()
    if not Zone.query.filter_by(name="A").first():
        db.session.add(Zone(name="A", rate_per_min=Decimal("1.50"), max_minutes=120))
    if not Zone.query.filter_by(name="B").first():
        db.session.add(Zone(name="B", rate_per_min=Decimal("1.00"), max_minutes=180))
    db.session.commit()

def ok(data=None, **meta):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    if meta:
        payload.update(meta)
    return jsonify(payload), 200

def err(msg, code=400):
    return jsonify({"success": False, "error": msg}), code

def now():
    return datetime.utcnow()

@app.get("/zones")
def list_zones():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page",5, type=int)
    sort = request.args.get("sort", "name")
    sort_map = {
        "name": func.lower(Zone.name).asc(),
        "id": Zone.id.asc(),
        "-name": func.lower(Zone.name).desc(),
        "-id": Zone.id.desc(),
    }
    order_clause = sort_map.get(sort, func.lower(Zone.name).asc())
    query = Zone.query.order_by(order_clause)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    zones = [zones.to_dict() for zones in pagination.items]
    return ok(
        zones,
        page=pagination.page,
        per_page=pagination.per_page,
        total_items=pagination.total,
        total_pages=pagination.pages,
    )

@app.post("/vehicles")
def create_vehicle():
    data = request.get_json() or {}
    plate = data.get("plate")
    user_id = data.get("user_id")
    if not plate or not user_id:
        return err("los campos plate y user_id son obligatorios", 400)
    user = User.query.get(user_id)
    if not user:
        return err("el usuario aun no esta registrado en Parkilite", 404)
    verifyVehicle = Vehicle.query.filter_by(user_id=user_id, plate=plate).first()
    if verifyVehicle:
        return err("Esta placa ya esta arriba en el sistema de parkilite", 404)
    vehicle = Vehicle(plate=plate, user_id=user_id)
    db.session.add(vehicle)
    db.session.commit()
    return jsonify({"success": True, "data": vehicle.to_dict(), "message": "Tu vehiculo ahora esta registrado en Parkilite"}), 201

@app.get("/vehicles")
def list_vehicles():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return err("Para que Parkilite pueda encontrar tu vehiculo necesita el userID", 400)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 5, type=int)
    sort = request.args.get("sort", "plate")
    sort_map = {
        "plate": func.lower(Vehicle.plate).asc(),
        "-plate": func.lower(Vehicle.plate).desc(),
        "id": Vehicle.id.asc(),
        "-id": Vehicle.id.desc(),
    }
    order_clause = sort_map.get(sort, func.lower(Vehicle.plate).asc())
    query = Vehicle.query.filter_by(user_id=user_id).order_by(order_clause)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    vehicles = [vehicle.to_dict() for vehicle in pagination.items]
    return ok(
        vehicles,
        page=pagination.page,
        per_page=pagination.per_page,
        total_items=pagination.total,
        total_pages=pagination.pages,
    )

@app.post("/sessions/start")
def sessions_start():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    plate = data.get("plate")
    zone_id = data.get("zone_id")

    if not user_id or not plate or not zone_id:
        return err("los campos user_id, plate y zone_id son obligatorios", 400)
    user = User.query.get(user_id)
    if not user:
        return err("El usuario no se encuentra registrado aún en Parkilite", 404)
    vehicle = Vehicle.query.filter_by(user_id=user_id, plate=plate).first()
    if not vehicle:
        return err("El usuario no cuenta con ningún vehiculo asociado con esta placa", 404)
    zone = Zone.query.get(zone_id)
    if not zone:
        return err("La zona aun no esta registrada en el Parkilite", 404)
    verifyActive = ParkingSession.query.filter_by(vehicle_id=vehicle.id, ended_at=None, status="active").first()
    if verifyActive:
        return err("No se puede tener dos sesiones activas de manera simultanea en Parkilite", 404)
    session = ParkingSession(
        user_id=user.id,
        vehicle_id=vehicle.id,
        zone_id=zone.id,
        started_at=now(),
        status="active",
    )
    db.session.add(session)
    db.session.commit()
    return ok(session.to_dict()), 201

@app.post("/sessions/stop")
def sessions_stop():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    session_id = data.get("session_id")
    if not user_id or not session_id:
        return err("los campos user_id y session_id son obligatorios", 400)
    session = ParkingSession.query.get(session_id)
    if not session:
        return err("La sesión no ha sido creada", 404)
    if session.status != "active":
        return err("La sesión ya no esta activa y fue cobrada con exito", 409)
    user = User.query.get(user_id)
    if not user:
        return err("El usuario no se encuentra registrado aun en Parkilite", 404)
    zone = Zone.query.get(session.zone_id)
    if not zone:
        return err("La sesion aún no ha sido creada", 500)
    session.ended_at = now()
    session.minutes = int (session.ended_at - session.started_at)
    session.rate = Decimal(str(zone.rate_per_min))
    session.cost = (Decimal(session.minutes) * session.rate)
    total = session.cost
    session.status = "inactive"
    if session.minutes > zone.max_minutes:
        total = (session.cost + Decimal("100.00"))
        status = "fined"

    session.cost_total = total
    current_balance = Decimal(str(user.balance or 0))

    if current_balance < total:
        session.status = "pending"
    else:
        user.balance = (current_balance - total)
    db.session.commit()
    return ok(session.to_dict())

if __name__ == "__main__":
    app.run(debug=True)

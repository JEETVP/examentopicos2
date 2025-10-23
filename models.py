from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint

db = SQLAlchemy()
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Numeric(10, 2), nullable=False, default=300)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    vehicles = db.relationship("Vehicle",back_populates="user",cascade="all, delete-orphan")
    sessions = db.relationship("ParkingSession",back_populates="user",cascade="all, delete-orphan")
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "balance": float(self.balance or 0),
            "vehicles": [v.to_dict() for v in self.vehicles.all()],
        }
    def __repr__(self) -> str:
        return f"<User {self.id} {self.username}>"


class Zone(db.Model):
    __tablename__ = "zones"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    rate_per_min = db.Column(db.Integer, nullable=False)     
    max_minutes = db.Column(db.Integer, nullable=False)  

    __table_args__ = (
        CheckConstraint("rate_per_min >= 0", name="validationrate"),
        CheckConstraint("max_minutes > 0", name="validationmaximum"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rate_per_min": self.rate_per_min,
            "max_minutes": self.max_minutes,
        }

    def __repr__(self) -> str:
        return f"<Zone {self.id} {self.name}>"

class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(10), unique = True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", back_populates="vehicles")
    sessions = db.relationship("ParkingSession",back_populates="vehicle",cascade="all, delete-orphan")
    def __repr__(self) -> str:
        return f"<Vehicle {self.id} {self.plate} u{self.user_id}>"

class ParkingSession(db.Model):
    __tablename__ = "parking_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    zone_id = db.Column(db.Integer, db.ForeignKey("zones.id"), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)  
    minutes = db.Column(db.Integer, nullable=True) 
    cost = db.Column(db.Numeric(10, 2), nullable=True) 
    cost_total = db.Column(db.Numeric(10, 2), nullable=True)  
    status = db.Column(db.String(50), nullable=False, default = "active")
    user = db.relationship("User", back_populates="sessions")
    vehicle = db.relationship("Vehicle", back_populates="sessions")
    zone = db.relationship("Zone")
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "vehicle_id": self.vehicle_id,
            "zone_id": self.zone_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "minutes": self.minutes,
            "cost": float(self.cost) if self.cost is not None else None,
            "cost_total": float(self.cost_total) if self.cost_total is not None else None,
            "status": self.status.value,
        }

    def __repr__(self) -> str:
        return f"<ParkingSession {self.id} v{self.vehicle_id} {self.status.value}>"

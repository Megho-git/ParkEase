from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import func

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    fullname = db.Column(db.String(100))
    address = db.Column(db.Text)
    pincode = db.Column(db.String(10))
    role = db.Column(db.String(20), default='user')

    reservations = db.relationship('Reservation', backref='user', lazy=True)


class ParkingLot(db.Model):
    __tablename__ = 'parking_lots'

    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100))
    address = db.Column(db.String(300))
    pin_code = db.Column(db.String(10))
    price_per_hour = db.Column(db.Float, nullable=False)
    available_spots = db.Column(db.Integer)
    spots = relationship("ParkingSpot", backref="lot", cascade="all, delete-orphan")

    @property
    def available_spots_count(self):
        return len([spot for spot in self.spots if spot.status == 'A'])

    @property
    def occupied_spots_count(self):
        return len([spot for spot in self.spots if spot.status == 'O'])

    @property
    def total_spots(self):
        return len(self.spots)

class ParkingSpot(db.Model):
    __tablename__ = 'parking_spots'

    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lots.id'), nullable=False)
    status = db.Column(db.String(1), nullable=False, default='A')
    reservations = db.relationship('Reservation', backref='spot', lazy=True)

class Reservation(db.Model):
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spots.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    parking_time = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_time = db.Column(db.DateTime, nullable=True)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fullname = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False)
    
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.email}>'

class ParkingLot(db.Model):
    __tablename__ = 'parking_lots'
    
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_spots(self):
        return len(self.spots)
    
    @property
    def available_spots_count(self):
        return len([s for s in self.spots if s.status == 'A'])
    
    @property
    def occupied_spots_count(self):
        return len([s for s in self.spots if s.status == 'O'])
    
    def __repr__(self):
        return f'<ParkingLot {self.prime_location_name}>'

class ParkingSpot(db.Model):
    __tablename__ = 'parking_spots'
    
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lots.id'), nullable=False)
    status = db.Column(db.String(1), default='A', nullable=False)
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    
    reservations = db.relationship('Reservation', backref='spot', lazy=True)
    
    def __repr__(self):
        return f'<ParkingSpot {self.id}>'

class Reservation(db.Model):
    __tablename__ = 'reservations'
    
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spots.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    parking_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    leaving_time = db.Column(db.DateTime, nullable=True)
    planned_start_time = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', backref='reservations', lazy=True)
    
    @property
    def is_active(self):
        return self.leaving_time is None
    
    @property
    def duration_hours(self):
        end_time = self.leaving_time or datetime.utcnow()
        return (end_time - self.parking_time).total_seconds() / 3600
    
    def __repr__(self):
        return f'<Reservation {self.id}>'
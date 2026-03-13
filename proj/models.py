# proj/models.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from proj import db

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from proj.login_manager import login_manager
import pytz
IST = pytz.timezone("Asia/Kolkata")


# IMPORTANT: import db from proj (do NOT create a new SQLAlchemy() here)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(15))
    role = db.Column(db.String(20))  # "patient" or "doctor"
    password_hash = db.Column(db.String(128))

    doctor = db.relationship("Doctor", back_populates="user", uselist=False)
    patient = db.relationship("Patient", back_populates="user", uselist=False)
    

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    


class Doctor(db.Model):
    __tablename__ = "doctor"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    working_hours_start = db.Column(db.Time, default='08:00:00')  # 8 AM
    working_hours_end = db.Column(db.Time, default='21:00:00')    # 9 PM
    days_off = db.Column(db.String(100), default='')  # Comma-separated days (0=Monday to 6=Sunday)


    # Add these fields if they don't exist
    disease = db.Column(db.String(200))  # Store the disease/condition
    symptoms = db.Column(db.Text)        # Store comma-separated symptoms


    user = db.relationship("User", back_populates="doctor")



class Patient(db.Model):
    __tablename__ = "patients"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    medical_history = db.Column(db.Text)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))

    # 1-to-1 relationship with User
    user = db.relationship("User", back_populates="patient")

class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)   # FK to Doctor
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)  # FK to Patients
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(50), default="Scheduled")

    # ✅ Correct relationships
    doctor = db.relationship("Doctor", backref="appointments")
    patient = db.relationship("Patient", backref="appointments")


# helper to check time conflicts (unchanged)
def check_appointment_conflict(doctor_id, appointment_date, start_time, end_time):
    conflicting_appointments = Appointment.query.filter_by(
        doctor_id=doctor_id, appointment_date=appointment_date
    ).filter(
        (Appointment.appointment_time >= start_time) &
        (Appointment.appointment_time < end_time)
    ).all()

    return len(conflicting_appointments) > 0


class Message(db.Model):
    __tablename__ = 'message'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys to users table
    sender_id = db.Column(
        db.Integer, 
        db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), 
        nullable=False
    )
    
    receiver_id = db.Column(
        db.Integer, 
        db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), 
        nullable=False
    )
    
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def ist_time(self):
        return self.timestamp.replace(tzinfo=pytz.utc).astimezone(IST)
    
    # Relationships
    sender = db.relationship(
        'User', 
        foreign_keys=[sender_id],
        backref=db.backref('sent_messages', lazy='dynamic', cascade='all, delete-orphan')
    )
    
    receiver = db.relationship(
        'User', 
        foreign_keys=[receiver_id],
        backref=db.backref('received_messages', lazy='dynamic', cascade='all, delete-orphan')
    )
    
    def __repr__(self):
        return f"<Message {self.id}: {self.sender_id} -> {self.receiver_id}>"
    

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
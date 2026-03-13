from flask import Blueprint, request, jsonify, redirect, url_for, flash
from proj import db
from proj.models import Appointment, Doctor, User, Patient
from datetime import datetime  # ✅ Added

appointment_blueprint = Blueprint('appointment', __name__)

@appointment_blueprint.route('/book-appointment', methods=['POST'])
def book_appointment():
    if request.is_json:  # ✅ If request is JSON (API call)
        data = request.get_json()
        patient_id = data.get('patient_id')
        doctor_id = data.get('doctor_id')
        appointment_date_str = data.get('appointment_date')
        appointment_time_str = data.get('appointment_time')
    else:  # ✅ If request is form-data (from HTML form)
        patient_id = request.form.get('patient_id')
        doctor_id = request.form.get('doctor_id')
        appointment_date_str = request.form.get('appointment_date')
        appointment_time_str = request.form.get('appointment_time')

    # Validate required fields
    if not all([patient_id, doctor_id, appointment_date_str, appointment_time_str]):
        if request.is_json:
            return jsonify({'error': 'Missing required fields'}), 400
        else:
            flash("⚠️ All fields are required!", "danger")
            return redirect(url_for('main.appointments'))

    # ✅ Convert strings to proper Python date/time
    appointment_date = datetime.strptime(appointment_date_str, "%Y-%m-%d").date()
    appointment_time = datetime.strptime(appointment_time_str, "%H:%M").time()

    # Check if patient & doctor exist
    patient = Patient.query.get(patient_id)
    doctor = Doctor.query.get(doctor_id)
    if not patient or not doctor:
        if request.is_json:
            return jsonify({'error': 'Patient or doctor not found'}), 404
        else:
            flash("⚠️ Patient or Doctor not found!", "danger")
            return redirect(url_for('main.appointments'))

    # Check for conflicts
    existing_appointment = Appointment.query.filter_by(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        appointment_time=appointment_time
    ).first()

    if existing_appointment:
        if request.is_json:
            return jsonify({'error': 'Appointment time slot is not available'}), 409
        else:
            flash("⚠️ Appointment time slot is not available!", "danger")
            return redirect(url_for('main.appointments'))

    # Book appointment
    new_appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        appointment_time=appointment_time
    )
    db.session.add(new_appointment)
    db.session.commit()

    if request.is_json:
        return jsonify({'message': 'Appointment booked successfully'}), 201
    else:
        flash("✅ Appointment booked successfully!", "success")
        return redirect(url_for('main.appointments'))
    


# Add this route to appoint_routes.py
@appointment_blueprint.route('/cancel-appointment/<int:appointment_id>', methods=['POST'])
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Check if user has permission to cancel this appointment
    if request.is_json:
        data = request.get_json()
        user_id = data.get('user_id')
    else:
        user_id = request.form.get('user_id')
    
    if not user_id:
        if request.is_json:
            return jsonify({'error': 'User ID required'}), 400
        else:
            flash("User ID required!", "danger")
            return redirect(url_for('main.appointments'))
    
    user = User.query.get(user_id)
    if not user:
        if request.is_json:
            return jsonify({'error': 'User not found'}), 404
        else:
            flash("User not found!", "danger")
            return redirect(url_for('main.appointments'))
    
    # Check permissions - patient can cancel their own appointments, doctor can cancel their appointments
    can_cancel = False
    if user.role == 'patient':
        patient = Patient.query.filter_by(user_id=user.id).first()
        if patient and appointment.patient_id == patient.id:
            can_cancel = True
    elif user.role == 'doctor':
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if doctor and appointment.doctor_id == doctor.id:
            can_cancel = True
    
    if not can_cancel:
        if request.is_json:
            return jsonify({'error': 'You do not have permission to cancel this appointment'}), 403
        else:
            flash("You do not have permission to cancel this appointment!", "danger")
            return redirect(url_for('main.appointments'))
    
    # Cancel the appointment
    appointment.status = "Cancelled"
    db.session.commit()
    
    if request.is_json:
        return jsonify({'message': 'Appointment cancelled successfully'}), 200
    else:
        flash("Appointment cancelled successfully!", "success")
        return redirect(url_for('main.appointments'))
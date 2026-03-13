from datetime import datetime, time, timedelta
from proj.models import Doctor, Appointment

def get_available_time_slots(doctor_id, appointment_date):
    """Get available time slots for a doctor on a specific date"""
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return []
    
    # Convert string date to datetime object if needed
    if isinstance(appointment_date, str):
        appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    
    # Get booked appointments for that day
    booked_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == appointment_date,
        Appointment.status == "Scheduled"
    ).all()
    
    booked_times = [apt.appointment_time for apt in booked_appointments]
    
    # Generate all possible time slots (30-minute intervals)
    time_slots = []
    current_time = datetime.combine(appointment_date, doctor.working_hours_start)
    end_time = datetime.combine(appointment_date, doctor.working_hours_end)
    
    while current_time < end_time:
        time_slot = current_time.time()
        
        # Check if time slot is available and within working hours
        if (time_slot not in booked_times and 
            time_slot >= doctor.working_hours_start and 
            time_slot < doctor.working_hours_end):
            time_slots.append(time_slot.strftime('%H:%M'))
        
        current_time += timedelta(minutes=30)
    
    return time_slots

def is_doctor_available(doctor_id, appointment_date, appointment_time):
    """Check if a doctor is available at a specific date and time"""
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return False
    
    # Check working hours
    if (appointment_time < doctor.working_hours_start or 
        appointment_time >= doctor.working_hours_end):
        return False
    
    # Check day off
    if doctor.days_off and str(appointment_date.weekday()) in doctor.days_off.split(','):
        return False
    
    # Check for existing appointments
    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == appointment_date,
        Appointment.appointment_time == appointment_time,
        Appointment.status == "Scheduled"
    ).first()
    
    return existing is None
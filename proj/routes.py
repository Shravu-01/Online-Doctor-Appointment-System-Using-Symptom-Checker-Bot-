import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import render_template, request, session, redirect, url_for, flash, Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required
from pathlib import Path
from flask_login import current_user
from proj import db
from proj.models import User, Doctor, Appointment, Patient
from proj.utils import send_appointment_email
from proj.messaging import store_message, get_messages_between_users
from flask import request, abort
import proj.socket_handlers  # ensure events are registered
from proj.models import Message
from datetime import datetime, date
import pytz
from flask import render_template_string
from flask import current_app
from jinja2 import TemplateNotFound
import mysql.connector
from proj.symptom_checker import SymptomChecker

# Initialize symptom checker after db and models are imported
symptom_checker = SymptomChecker(db, Doctor)




# Define Indian Standard Time (IST)
IST = pytz.timezone("Asia/Kolkata")

# ✅ If send_notification and conflict check are in another file (utils.py), import them
# from proj.utils import send_notification, check_appointment_conflict

main = Blueprint("main", __name__)


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")  # ✅ match login.html
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()  # ✅ login by username

        if user and user.check_password(password):
            login_user(user, remember=True)
            if user.role == "doctor":
                return redirect(url_for("main.doctor_dashboard"))
            else:
                return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))

@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        mobile = request.form.get("mobile")
        role = request.form.get("role")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("main.register"))

        # Check duplicate email in users table
        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for("main.register"))

        # Check duplicate username
        if User.query.filter_by(username=username).first():
            flash("Username already taken!", "danger")
            return redirect(url_for("main.register"))

        # Create new user
        user = User(username=username, email=email, mobile=mobile, role=role)
        user.set_password(password)

        db.session.add(user)
        db.session.flush()  # ✅ ensures user.id is available before commit

        # ✅ If doctor, either link to existing doctor row or create a new one
        if role == "doctor":
            specialization = request.form.get("specialization", "General")

            # 🔑 Check if this doctor already exists in doctors table by email
            existing_doc = Doctor.query.filter_by(email=email).first()
            if existing_doc:
                # Link the newly created user to the existing doctor record
                existing_doc.user_id = user.id
            else:
                # Otherwise create a fresh Doctor record
                doctor = Doctor(
                    name=username,  # or a separate full-name field if you collect it
                    specialization=specialization,
                    email=email,
                    user_id=user.id
                )
                db.session.add(doctor)

        # ✅ If patient, also create entry in Patient table
        elif role == "patient":
            patient = Patient(
                user_id=user.id,
                medical_history="",
                age=0,
                gender="Not specified"
            )
            db.session.add(patient)

        db.session.commit()

        flash("You have been registered! Please login.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html")


@main.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "patient":
        # Get patient's appointments
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        appointments = []
        doctors_count = 0
        
        if patient:
            appointments = Appointment.query.filter_by(patient_id=patient.id).all()
            # Count unique doctors the patient has appointments with
            doctors_count = len(set(appt.doctor_id for appt in appointments))
        
        return render_template(
            "dashboard.html",
            appointments=appointments,
            doctors_count=doctors_count,
            current_user=current_user
        )
    else:
        # Handle doctor or admin dashboard
        return render_template("dashboard.html", current_user=current_user)
    

@main.route("/doctor_dashboard", methods=["GET", "POST"])
@login_required
def doctor_dashboard():
    # ✅ Find the doctor row that belongs to this logged-in user
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        flash("Doctor profile not found!", "danger")
        return redirect(url_for("main.dashboard"))

    # 🔍 Debug info
    print(f"🔍 Current User ID: {current_user.id}")
    print(f"🔍 Found Doctor: ID={doctor.id}, Name={doctor.name}, User ID={doctor.user_id}")

    # ✅ Get the selected date from query string or form, fallback to today
    selected_date_str = request.args.get("date")
    if not selected_date_str and request.method == "POST":
        selected_date_str = request.form.get("date")

    try:
        selected_date = (
            datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            if selected_date_str else date.today()
        )
    except ValueError:
        flash("Invalid date format! Showing today's date.", "warning")
        selected_date = date.today()

    # ✅ Query appointments for this doctor and selected date
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == selected_date
    ).all()

    # 🔍 More debug output
    print(f"🚨 Querying appointments for doctor_id={doctor.id} on date={selected_date}")
    print(f"🚨 Found {len(appointments)} appointments")

    # 🔍 Show all appointments for this doctor (any date)
    all_doctor_appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    print(f"🔍 All appointments for doctor {doctor.id}: {len(all_doctor_appointments)}")
    for appt in all_doctor_appointments:
        print(f"   - Appointment ID: {appt.id}, Date: {appt.appointment_date}, Time: {appt.appointment_time}")

    return render_template(
        "doctor_dashboard.html",
        appointments=appointments,
        selected_date=selected_date,
        doctor=doctor
    )


@main.route("/appointments")
@login_required
def appointments():
    if current_user.role == "patient":
        if current_user.patient:
            appointments = Appointment.query.filter_by(
                patient_id=current_user.patient.id
            ).all()
        else:
            appointments = []
    elif current_user.role == "doctor":
        if current_user.doctor:
            appointments = Appointment.query.filter_by(
                doctor_id=current_user.doctor.id
            ).all()
        else:
            appointments = []
    else:
        appointments = []
        

    doctors = Doctor.query.all()  # ✅ make doctors available for dropdown
    return render_template("appointments.html", appointments=appointments, doctors=doctors)



@main.route("/book-appointment", methods=["GET", "POST"])
@login_required
def book_appointment():
    doctors = Doctor.query.all()  # Fetch all doctors for dropdown
    pre_selected_doctor_id = None

    doctor_id_from_url = request.args.get('doctor_id')
    if doctor_id_from_url:
        try:
            pre_selected_doctor_id = int(doctor_id_from_url)
        except ValueError:
            pass
    
    # Also check session for selected doctor (alternative method)
    if not pre_selected_doctor_id and session.get('selected_doctor_id'):
        pre_selected_doctor_id = session.get('selected_doctor_id')
        # Clear it from session after retrieving
        session.pop('selected_doctor_id', None)
    
    # Get the pre-selected doctor object if ID exists
    pre_selected_doctor = None
    if pre_selected_doctor_id:
        pre_selected_doctor = Doctor.query.get(pre_selected_doctor_id)


    if request.method == "POST":
        data = request.form
        doctor_id_from_form = data.get("doctor_id")  # This might be Doctor.id, not User.id

        # Get the doctor record to access their user_id
        doctor = Doctor.query.get(doctor_id_from_form)
        if not doctor:
            flash("Invalid doctor selection!", "danger")
            return redirect(url_for("main.appointments"))

        # Use the doctor's user_id (which matches users.id)
        doctor_user_id = doctor.user_id

        # get the patient's record linked to this user
        patient = Patient.query.filter_by(user_id=current_user.id).first()

        if not patient:
            flash("You are not registered as a patient!", "danger")
            return redirect(url_for("main.appointments"))

        appointment_date = datetime.strptime(
            data.get("appointment_date"), "%Y-%m-%d"
        ).date()
        appointment_time = datetime.strptime(
            data.get("appointment_time"), "%H:%M"
        ).time()


         # ✅ NEW: Validate time slot (8 AM to 9 PM) - ADD THIS SECTION
        time_hour = appointment_time.hour
        if time_hour < 8 or time_hour >= 21:
            flash("❌ Appointments can only be scheduled between 8 AM and 9 PM!", "danger")
            return redirect(url_for("main.appointments"))

        # ✅ NEW: Validate doctor's working hours - ADD THIS SECTION
        if doctor.working_hours_start and doctor.working_hours_end:
            if (appointment_time < doctor.working_hours_start or 
                appointment_time >= doctor.working_hours_end):
                flash(f"❌ Dr. {doctor.name} is only available from {doctor.working_hours_start.strftime('%I:%M %p')} to {doctor.working_hours_end.strftime('%I:%M %p')}!", "danger")
                return redirect(url_for("main.appointments"))

        # ✅ NEW: Check if appointment date is not a day off for doctor - ADD THIS SECTION
        if doctor.days_off:
            day_off_list = doctor.days_off.split(',')
            if str(appointment_date.weekday()) in day_off_list:
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                flash(f"❌ Dr. {doctor.name} is not available on {day_names[appointment_date.weekday()]}s!", "danger")
                return redirect(url_for("main.appointments"))

        # ✅ NEW: Check for existing appointments (updated to check status) - UPDATE THIS SECTION
        existing_appointment = Appointment.query.filter_by(
            doctor_id=doctor.id,
            appointment_date=appointment_date,
            appointment_time=appointment_time
        ).filter(Appointment.status != "Cancelled").first()  # Only check non-cancelled appointments

        if existing_appointment:
            flash("❌ This time slot is already booked! Please choose another time.", "danger")
            return redirect(url_for("main.appointments"))


        # ✅ Create new appointment using doctor's USER ID
        new_appointment = Appointment(
            doctor_id=doctor.id, # Use the doctor's user_id
            patient_id=patient.id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status="Scheduled",
        )
        db.session.add(new_appointment)
        db.session.commit()

        # ✅ Send confirmation email
        send_appointment_email(
            patient.user.email, doctor.name, appointment_date, appointment_time
        )

        flash("Appointment booked successfully!", "success")
        return redirect(url_for("main.appointments"))
    
    
    # For GET requests
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    appointments = []
    if patient:
        appointments = Appointment.query.filter_by(patient_id=patient.id).all()
    
    return render_template(
        "appointments.html", 
        doctors=doctors, 
        appointments=appointments,
        pre_selected_doctor=pre_selected_doctor
    )

@main.route("/get-appointments")
@login_required
def get_appointments():
    events = []

    if current_user.role == "patient":
        appointments = Appointment.query.filter_by(patient_id=current_user.patient.id).all()
    elif current_user.role == "doctor":
        appointments = Appointment.query.filter_by(doctor_id=current_user.doctor.id).all()
    else:  # admin
        appointments = Appointment.query.all()

    for appt in appointments:
        events.append(
            {
                "title": f"Dr. {appt.doctor.name}",
                "start": f"{appt.appointment_date}T{appt.appointment_time}",
            }
        )

    return jsonify(events)



# Add this temporary route for testing
@main.route("/debug_appointments")
@login_required
def debug_appointments():
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    all_appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    return jsonify([{
        'id': a.id,
        'doctor_id': a.doctor_id,
        'patient_id': a.patient_id,
        'date': str(a.appointment_date),
        'time': str(a.appointment_time)
    } for a in all_appointments])



# Add this route to routes.py for the main blueprint
@main.route("/cancel-appointment/<int:appointment_id>", methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Check permissions
    can_cancel = False
    if current_user.role == 'patient':
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if patient and appointment.patient_id == patient.id:
            can_cancel = True
    elif current_user.role == 'doctor':
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if doctor and appointment.doctor_id == doctor.id:
            can_cancel = True
    
    if not can_cancel:
        flash("You do not have permission to cancel this appointment!", "danger")
        return redirect(url_for('main.appointments'))
    
    # Cancel the appointment
    appointment.status = "Cancelled"
    db.session.commit()
    
    flash("Appointment cancelled successfully!", "success")
    return redirect(url_for('main.appointments'))



@main.route("/send_message", methods=["POST"])
@login_required
def send_message():
    try:
        data = request.get_json()
        message_text = data.get("message")
        receiver_id = data.get("receiver_id")

        # Use USER IDs directly for messaging (not doctor/patient IDs)
        sender_id = current_user.id  # This is the USER ID

        if not message_text or not receiver_id:
            return jsonify({"error": "Invalid data"}), 400

        # Store message in the database using USER IDs
        new_message = Message(
            sender_id=sender_id,  # USER ID
            receiver_id=receiver_id,  # USER ID  
            message=message_text
        )
        db.session.add(new_message)
        db.session.commit()

        return jsonify({"success": True, "message": "Message sent successfully!"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    


@main.route("/get_messages", methods=["GET"])
@login_required
def get_messages():
    # Get the other user's USER ID (not doctor/patient ID)
    other_user_id = request.args.get("other_user_id", type=int)
    
    if not other_user_id:
        return jsonify({"error": "other_user_id required"}), 400

    # Get messages between current user and other user (using USER IDs)
    messages = get_messages_between_users(current_user.id, other_user_id)
    
    return jsonify([{
        "message": message.message, 
        "timestamp": message.timestamp,
        "sender_id": message.sender_id,
        "is_me": message.sender_id == current_user.id
    } for message in messages]), 200


@main.route('/chat/<int:doctor_id>/<int:patient_id>')
@login_required
def chat(doctor_id, patient_id):
    """Chat room for doctor-patient communication with proper error handling"""
    try:
        print(f"\n🔍 CHAT ACCESS ATTEMPT:")
        print(f"   Doctor ID: {doctor_id}")
        print(f"   Patient ID: {patient_id}")
        print(f"   Current User ID: {current_user.id}")
        print(f"   Current User Role: {current_user.role}")
        
        # Check if users exist
        doctor_user = User.query.get(doctor_id)
        patient_user = User.query.get(patient_id)
        
        if not doctor_user:
            flash(f"Doctor with ID {doctor_id} doesn't exist!", "danger")
            print(f"❌ Doctor {doctor_id} not found")
            return redirect(url_for("main.dashboard"))
        
        if not patient_user:
            flash(f"Patient with ID {patient_id} doesn't exist!", "danger")
            print(f"❌ Patient {patient_id} not found")
            return redirect(url_for("main.dashboard"))
        
        # Verify roles
        if doctor_user.role != 'doctor':
            flash(f"User {doctor_user.username} is not a doctor!", "danger")
            print(f"❌ User {doctor_id} is not a doctor (role: {doctor_user.role})")
            return redirect(url_for("main.dashboard"))
        
        if patient_user.role != 'patient':
            flash(f"User {patient_user.username} is not a patient!", "danger")
            print(f"❌ User {patient_id} is not a patient (role: {patient_user.role})")
            return redirect(url_for("main.dashboard"))
        
        # Check permissions
        if current_user.role == 'doctor' and current_user.id != doctor_id:
            flash("You are not authorized to access this chat as a doctor", "danger")
            print(f"❌ Doctor authorization failed")
            return redirect(url_for("main.doctor_dashboard"))
        
        if current_user.role == 'patient' and current_user.id != patient_id:
            flash("You are not authorized to access this chat as a patient", "danger")
            print(f"❌ Patient authorization failed")
            return redirect(url_for("main.dashboard"))
        
        # Get doctor and patient objects for names
        doctor = Doctor.query.filter_by(user_id=doctor_id).first()
        patient = Patient.query.filter_by(user_id=patient_id).first()
        
        if not doctor:
            flash("Doctor profile not found!", "danger")
            return redirect(url_for("main.dashboard"))
        
        if not patient:
            flash("Patient profile not found!", "danger")
            return redirect(url_for("main.dashboard"))
        
        # Get messages between these users
        messages = Message.query.filter(
            ((Message.sender_id == doctor_id) & (Message.receiver_id == patient_id)) |
            ((Message.sender_id == patient_id) & (Message.receiver_id == doctor_id))
        ).order_by(Message.timestamp.asc()).all()
        
        # Create consistent room name (sorted IDs)
        user_ids = sorted([doctor_id, patient_id])
        room = f"chat_{user_ids[0]}_{user_ids[1]}"
        
        print(f"✅ Chat authorized:")
        print(f"   Doctor: {doctor.name} (User ID: {doctor_id})")
        print(f"   Patient: {patient_user.username} (User ID: {patient_id})")
        print(f"   Room: {room}")
        print(f"   Messages in history: {len(messages)}")
        
        
        return render_template('chat.html',
            doctor_id=doctor_id,
            patient_id=patient_id,
            messages=messages,
            role=current_user.role,
            user_id=current_user.id,
            doctor_name=doctor.name,
            patient_name=patient_user.username,
            current_time=datetime.now().strftime('%H:%M'),
            room=room
        )
        
    except Exception as e:
        print(f"❌ Error in chat route: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Error accessing chat room: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))
    
    
@main.route("/")
def home():
    return render_template('index.html')
    
# routes.py - ADD THESE NEW ROUTES

@main.route("/book_appointment/<int:doctor_id>")
@login_required
def book_appointment_from_chatbot(doctor_id):
    """Redirect to appointment booking with pre-selected doctor"""
    if current_user.role != "patient":
        flash("Only patients can book appointments.", "warning")
        return redirect(url_for('main.dashboard'))
    
    # Verify doctor exists
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        flash("Doctor not found.", "danger")
        return redirect(url_for('main.symptom_chat'))
    
    # Store doctor info in session for pre-selection
    session['selected_doctor_id'] = doctor_id
    session['from_chatbot'] = True
    
    # Redirect to your existing appointment booking page
    # Adjust this based on your actual appointment booking route
    return redirect(url_for('main.book_appointment', doctor_id=doctor_id))

@main.route("/chatbot/symptoms", methods=["GET"])
@login_required
def get_categorized_symptoms():
    """Get all symptoms categorized for interactive selection"""
    try:
        # Check if user is patient
        if current_user.role != "patient":
            return jsonify({
                'success': False,
                'error': 'This feature is only available for patients.'
            }), 403
        
        # Define all 26 symptoms with IDs
        all_symptoms = {
            1: "chest tightness", 2: "wheezing", 3: "sensitivity to light",
            4: "headache", 5: "restlessness", 6: "trouble sleeping",
            7: "fatigue", 8: "nausea", 9: "fever", 10: "cough",
            11: "difficulty breathing", 12: "shortness of breath",
            13: "high blood pressure", 14: "dizziness",
            15: "blurred vision", 16: "abdominal pain",
            17: "loss of appetite", 18: "rash", 19: "dry skin",
            20: "increased thirst", 21: "frequent urination",
            22: "itching", 23: "night sweats", 24: "weight loss",
            25: "chronic cough", 26: "sore throat"
        }
        
        # Categorize symptoms
        categorized = {
            "Respiratory & Chest": {},
            "Head & Neurological": {},
            "General & Systemic": {},
            "Abdominal & Digestive": {},
            "Skin Related": {},
            "Metabolic & Urinary": {},
            "Cardiovascular": {},
            "Sleep & Mental": {}
        }
        
        # Map symptoms to categories
        category_mapping = {
            "Respiratory & Chest": [1, 2, 10, 11, 12, 25, 26],
            "Head & Neurological": [3, 4, 14, 15],
            "General & Systemic": [7, 9, 23, 24],
            "Abdominal & Digestive": [8, 16, 17],
            "Skin Related": [18, 19, 22],
            "Metabolic & Urinary": [20, 21],
            "Cardiovascular": [13],
            "Sleep & Mental": [5, 6]
        }
        
        for category, symptom_ids in category_mapping.items():
            for symptom_id in symptom_ids:
                if symptom_id in all_symptoms:
                    categorized[category][str(symptom_id)] = all_symptoms[symptom_id]
        
        return jsonify({
            'success': True,
            'symptoms': categorized,
            'total_count': len(all_symptoms)
        })
        
    except Exception as e:
        print(f"Error getting symptoms: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to load symptoms'
        }), 500

@main.route("/chatbot/analyze", methods=["POST"])
@login_required
def analyze_selected_symptoms():
    """Analyze selected symptoms and recommend doctors"""
    try:
        # Check if user is patient
        if current_user.role != "patient":
            return jsonify({
                'success': False,
                'error': 'This feature is only available for patients.'
            }), 403
        
        data = request.json
        symptom_ids = data.get('symptom_ids', [])
        
        if not symptom_ids:
            return jsonify({
                'success': False,
                'error': 'No symptoms selected'
            }), 400
        
        # Convert to integers
        try:
            symptom_ids = [int(sid) for sid in symptom_ids]
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid symptom IDs'
            }), 400
        
        # Validate symptom IDs (1-26)
        valid_ids = list(range(1, 27))
        invalid_ids = [sid for sid in symptom_ids if sid not in valid_ids]
        
        if invalid_ids:
            return jsonify({
                'success': False,
                'error': f'Invalid symptom IDs: {invalid_ids}'
            }), 400
        
        print(f"Analyzing selected symptoms: {symptom_ids}")
        
        # Get all doctors
        doctors = Doctor.query.all()
        
        matched_doctors = []
        
        # Symptom ID to name mapping for display
        symptom_names = {
            1: "chest tightness", 2: "wheezing", 3: "sensitivity to light",
            4: "headache", 5: "restlessness", 6: "trouble sleeping",
            7: "fatigue", 8: "nausea", 9: "fever", 10: "cough",
            11: "difficulty breathing", 12: "shortness of breath",
            13: "high blood pressure", 14: "dizziness",
            15: "blurred vision", 16: "abdominal pain",
            17: "loss of appetite", 18: "rash", 19: "dry skin",
            20: "increased thirst", 21: "frequent urination",
            22: "itching", 23: "night sweats", 24: "weight loss",
            25: "chronic cough", 26: "sore throat"
        }
        
        for doctor in doctors:
            if doctor.symptoms:
                # Parse doctor's symptoms (comma-separated string)
                doctor_symptom_names = [s.strip().lower() for s in doctor.symptoms.split(',')]
                
                # Convert doctor's symptom names to IDs
                doctor_symptom_ids = []
                for symptom_name in doctor_symptom_names:
                    # Find symptom ID by name
                    for sid, name in symptom_names.items():
                        if name.lower() == symptom_name.lower():
                            doctor_symptom_ids.append(sid)
                            break
                
                # Calculate match
                matched_ids = set(symptom_ids) & set(doctor_symptom_ids)
                match_count = len(matched_ids)
                
                if match_count > 0:
                    match_percentage = (match_count / len(symptom_ids)) * 100
                    
                    # Get matched symptom names
                    matched_symptom_names = []
                    for sid in matched_ids:
                        if sid in symptom_names:
                            matched_symptom_names.append(symptom_names[sid])
                    
                    matched_doctors.append({
                        'doctor_id': doctor.id,
                        'name': doctor.name,
                        'specialization': doctor.specialization,
                        'disease': doctor.disease,
                        'email': doctor.email,
                        'match_percentage': match_percentage,
                        'matched_symptoms_count': match_count,
                        'matched_symptoms': matched_symptom_names
                    })
        
        # Sort by match percentage
        matched_doctors.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        # Prepare response
        if matched_doctors:
            return jsonify({
                'success': True,
                'message': f"Found {len(matched_doctors)} doctor(s) matching your {len(symptom_ids)} symptoms.",
                'recommendations': matched_doctors[:5],  # Top 5 matches
                'total_matches': len(matched_doctors),
                'selected_symptoms_count': len(symptom_ids)
            })
        else:
            # No matches found, return some general doctors
            general_doctors = Doctor.query.limit(3).all()
            recommendations = []
            
            for doctor in general_doctors:
                recommendations.append({
                    'doctor_id': doctor.id,
                    'name': doctor.name,
                    'specialization': doctor.specialization,
                    'disease': doctor.disease,
                    'email': doctor.email,
                    'match_percentage': 0,
                    'matched_symptoms_count': 0,
                    'matched_symptoms': [],
                    'reason': 'General consultation recommended'
                })
            
            return jsonify({
                'success': True,
                'message': "No exact matches found. Here are some doctors for general consultation:",
                'recommendations': recommendations,
                'total_matches': 0,
                'selected_symptoms_count': len(symptom_ids)
            })
            
    except Exception as e:
        print(f"Error analyzing selected symptoms: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to analyze symptoms'
        }), 500



@main.route("/symptom_chat")
@login_required
def symptom_chat():
    """Symptom checker chat interface"""
    if current_user.role != "patient":
        flash("This feature is only available for patients.", "warning")
        return redirect(url_for('main.dashboard'))
    
    return render_template("symptom_chat.html")


# routes.py (updated section)
@main.route('/analyze_symptoms', methods=['POST'])
def analyze_symptoms():
    try:
        data = request.get_json()
        user_input = data.get('symptoms', '').strip()
        user_id = data.get('user_id')  # Optional user ID for context
        
        if not user_input:
            return jsonify({'error': 'Please describe your symptoms'}), 400
        
        # Use the smart analysis instead of direct symptom analysis
        result = symptom_checker.smart_analyze_message(user_input, user_id)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in symptom analysis: {str(e)}")
        return jsonify({
            'error': 'Sorry, I encountered an error. Please try again.',
            'message_type': 'error'
        }), 500
    

    
    
@main.route("/debug-template")
def debug_template():
    try:
        print("🔍 Starting template render...")
        
        # Test 1: Check if template file exists and can be read
        import os
        from flask import current_app
        
        template_path = os.path.join(current_app.template_folder, 'index.html')
        print(f"📁 Template path: {template_path}")
        print(f"📁 File exists: {os.path.exists(template_path)}")
        
        # Read file directly
        with open(template_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        print(f"📄 File content length: {len(file_content)}")
        print(f"📄 First 100 chars: {file_content[:100]}")
        
        # Test 2: Try rendering
        result = render_template('index.html')
        print(f"✅ Render result length: {len(result)}")
        print(f"✅ First 100 chars of result: {result[:100]}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"ERROR: {str(e)}", 500
    

    
@main.route("/list-routes")
def list_routes():
    import urllib.parse
    from flask import url_for
    
    output = []
    for rule in current_app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods))
        line = f"{rule.endpoint:50} {methods:20} {rule}"
        output.append(line)
    
    return "<pre>" + "\n".join(sorted(output)) + "</pre>"

@main.route("/test-render")
def test_render():
    # Use render_template_string with the file content
    import os
    from flask import current_app
    
    template_path = os.path.join(current_app.template_folder, 'index.html')
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    return render_template_string(template_content)

@main.route("/check-file")
def check_file():
    import os
    from flask import current_app
    
    template_path = os.path.join(current_app.template_folder, 'index.html')
    
    # Check file properties
    file_exists = os.path.exists(template_path)
    file_size = os.path.getsize(template_path) if file_exists else 0
    
    # Try to read content
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        readable = True
    except Exception as e:
        content = f"Error reading: {e}"
        readable = False
    
    return f"""
    <h1>File Debug Info</h1>
    <p><strong>Path:</strong> {template_path}</p>
    <p><strong>Exists:</strong> {file_exists}</p>
    <p><strong>Size:</strong> {file_size} bytes</p>
    <p><strong>Readable:</strong> {readable}</p>
    <p><strong>Content preview:</strong></p>
    <pre>{content[:500] if readable else content}</pre>
    <p><strong>Content length:</strong> {len(content) if readable else 'N/A'}</p>
    """

@main.route("/create-index")
def create_index():
    import os
    from flask import current_app
    
    template_path = os.path.join(current_app.template_folder, 'index.html')
    
    # Create the file with content
    content = """<!DOCTYPE html>
<html>
<head>
    <title>PROGRAMMATIC TEST</title>
</head>
<body style="background: blue; color: white; font-size: 30px;">
    <h1>🔵 BLUE PAGE - CREATED BY CODE</h1>
    <p>This file was created programmatically!</p>
</body>
</html>"""
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return f"File created at: {template_path}<br>Size: {len(content)} bytes"



@main.route("/debug_database")
@login_required
def debug_database():
    """Debug route to check all doctors and patients"""
    doctors = Doctor.query.all()
    patients = Patient.query.all()
    
    doctor_list = []
    for doc in doctors:
        doctor_list.append({
            'id': doc.id,
            'name': doc.name,
            'user_id': doc.user_id,
            'email': doc.email
        })
    
    patient_list = []
    for pat in patients:
        patient_list.append({
            'id': pat.id, 
            'user_id': pat.user_id,
            'username': pat.user.username if pat.user else 'No user'
        })
    
    appointments = Appointment.query.all()
    appointment_list = []
    for appt in appointments:
        appointment_list.append({
            'id': appt.id,
            'doctor_id': appt.doctor_id,
            'patient_id': appt.patient_id,
            'date': str(appt.appointment_date)
        })
    
    return jsonify({
        'doctors': doctor_list,
        'patients': patient_list, 
        'appointments': appointment_list
    })

@main.route("/test_patient_chat")
@login_required
def test_patient_chat():
    """Test route for patient to chat with a specific doctor"""
    if current_user.role != "patient":
        return "This route is for patients only"
    
    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        return "Patient profile not found"
    
    # Get the first doctor from database for testing
    doctor = Doctor.query.first()
    if not doctor:
        return "No doctors found in database"
    
    return redirect(url_for('main.chat', doctor_id=doctor.id, patient_id=patient.id))

@main.route("/debug-routes")
def debug_routes():
    """Debug route to see all available routes"""
    routes = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint.startswith('main.'):
            routes.append(f"{rule.endpoint}: {rule.rule}")
    
    return "<br>".join(sorted(routes))

@main.route("/debug-chat-routes")
def debug_chat_routes():
    routes = []
    for rule in current_app.url_map.iter_rules():
        if 'chat' in rule.endpoint.lower():
            routes.append(f"{rule.endpoint}: {rule.rule}")
    return "<br>".join(sorted(routes))

@main.route("/test-socket")
def test_socket():
    """Test Socket.IO connection"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Socket.IO Test</title>
        <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    </head>
    <body>
        <h1>Socket.IO Test</h1>
        <div id="status">Disconnected</div>
        <script>
            const socket = io();
            socket.on('connect', () => {
                document.getElementById('status').innerHTML = 'Connected!';
                console.log('Connected');
            });
            socket.on('disconnect', () => {
                document.getElementById('status').innerHTML = 'Disconnected';
            });
        </script>
    </body>
    </html>
    """


@main.route("/test_chat_doctor")
@login_required
def test_chat_doctor():
    """Test chat for doctors"""
    if current_user.role != "doctor":
        return "Doctors only"
    
    # Get the first patient for testing
    patient = Patient.query.first()
    if not patient:
        return "No patients found"
    
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    
    return redirect(url_for('main.chat', 
        doctor_id=current_user.id, 
        patient_id=patient.user_id))

@main.route("/test_chat_patient")
@login_required
def test_chat_patient():
    """Test chat for patients"""
    if current_user.role != "patient":
        return "Patients only"
    
    # Get the first doctor for testing
    doctor = Doctor.query.first()
    if not doctor:
        return "No doctors found"
    
    return redirect(url_for('main.chat',
        doctor_id=doctor.user_id,
        patient_id=current_user.id))

@main.route("/debug_socket_rooms")
def debug_socket_rooms():
    """Debug Socket.IO rooms"""
    from proj.socket_handlers import active_users_by_room
    
    rooms_info = {}
    for room, users in active_users_by_room.items():
        rooms_info[room] = [{"user_id": u["user_id"], "sid": u["sid"][:10]} for u in users]
    
    return jsonify({
        "total_rooms": len(rooms_info),
        "rooms": rooms_info
    })


@main.route("/test_db_connection")
def test_db_connection():
    """Test database connection and message storage"""
    try:
        # Test 1: Basic connection
        from proj import db
        result = db.session.execute("SELECT 1").fetchone()
        
        # Test 2: Count messages
        message_count = Message.query.count()
        
        # Test 3: Try to insert a test message
        test_message = Message(
            sender_id=1,
            receiver_id=2,
            message="Test message from route",
            timestamp=datetime.utcnow()
        )
        db.session.add(test_message)
        db.session.commit()
        
        # Test 4: Verify it was saved
        saved_message = Message.query.filter_by(message="Test message from route").first()
        
        return jsonify({
            "status": "success",
            "db_connection": "OK",
            "message_count": message_count,
            "test_insert": "OK" if saved_message else "FAILED",
            "test_message_id": saved_message.id if saved_message else None
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
    

@main.route("/test_save_message", methods=["POST"])
def test_save_message():
    """Direct test of message saving"""
    try:
        data = request.json
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")
        message_text = data.get("message")
        
        new_message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message_text,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(new_message)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message_id": new_message.id,
            "sender_id": new_message.sender_id,
            "receiver_id": new_message.receiver_id,
            "message": new_message.message
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
    


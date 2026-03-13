#Do Not Run Directly
#Run using cmd through the project directory 
#python -m proj.utils (Run in bash)

from flask_mail import Message
from proj import mail

def send_appointment_email(user_email, doctor_name, date, time):
    msg = Message(
        subject="Appointment Confirmed",
        sender="truehealhealthtech@gmail.com",   # your clinic email
        recipients=[user_email],
        body=f"Your appointment with Dr. {doctor_name} is confirmed for {date} at {time}."
    )
    mail.send(msg)

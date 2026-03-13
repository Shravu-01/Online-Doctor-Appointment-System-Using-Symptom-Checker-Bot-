from datetime import datetime, timedelta

class Doctor:
    def __init__(self, id, name, working_hours, days_off):
        self.id = id
        self.name = name
        self.working_hours = working_hours
        self.days_off = days_off

    def is_available(self, date_time):
        # Check if the doctor is available on the given date and time
        if date_time.weekday() in self.days_off:
            return False
        if not (self.working_hours[0] <= date_time.hour < self.working_hours[1]):
            return False
        return True

class AppointmentScheduler:
    def __init__(self, doctors):
        self.doctors = doctors
        self.appointments = []

    def generate_time_slots(self, doctor, date):
        # Generate available time slots for the given doctor and date
        time_slots = []
        start_time = datetime(date.year, date.month, date.day, doctor.working_hours[0])
        end_time = datetime(date.year, date.month, date.day, doctor.working_hours[1])
        while start_time < end_time:
            if doctor.is_available(start_time):
                time_slots.append(start_time)
            start_time += timedelta(minutes=30)  # Assuming 30 minutes appointment duration
        return time_slots

    def book_appointment(self, doctor, date_time):
        # Book an appointment for the given doctor and date/time
        if doctor.is_available(date_time):
            self.appointments.append((doctor.id, date_time))
            return True
        return False

# Example usage
doctor = Doctor(1, 'John Doe', (9, 17), [5, 6])  # 9am to 5pm, Saturday and Sunday off
scheduler = AppointmentScheduler([doctor])

# Minimal change: choose a weekday if today is a day off
date = datetime.now().date()
while date.weekday() in doctor.days_off:
    date += timedelta(days=1)

time_slots = scheduler.generate_time_slots(doctor, date)
print('Available time slots:')
for time_slot in time_slots:
    print(time_slot)

# Book an appointment at 10am
appointment_time = datetime(date.year, date.month, date.day, 10)
if scheduler.book_appointment(doctor, appointment_time):
    print('Appointment booked successfully!')
else:
    print('Failed to book appointment!')

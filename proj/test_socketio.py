from flask import Flask
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config["SECRET_KEY"] = "TrueHeal1848HealthTech!"
socketio = SocketIO(app, cors_allowed_origins="*")


@socketio.on("connect")
def handle_connect():
    print("Client connected")
    emit("message", "Welcome to the Doctor Appointment System!")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


@socketio.on("join_room")
def handle_join(data):
    room = data["room"]
    join_room(room)
    emit("message", f"Someone joined {room}", room=room)


@socketio.on("send_message")
def handle_send_message(data):
    """
    Expected data:
    {
        "room": "chat_doctorId_patientId",
        "message": "Hello",
        "sender": "patient_1"  # or "doctor_5"
    }
    """
    room = data["room"]
    message = data["message"]
    sender = data.get("sender", "Anonymous")

    print(f"[{room}] {sender}: {message}")

    # Emit structured data to everyone in the room
    emit("new_message", {"message": message, "sender": sender}, room=room)


if __name__ == "__main__":
    socketio.run(app, host="localhost", port=5000, debug=True)

# proj/socket_handlers.py - FIXED VERSION

from flask_socketio import join_room, emit, leave_room, rooms
from flask import request
from flask_login import current_user
from proj import socketio, db
from proj.models import Message
from datetime import datetime
import pytz
IST = pytz.timezone("Asia/Kolkata")

# Store active users by room
active_users_by_room = {}


def create_room_name(doctor_id, patient_id):
    """Create a consistent room name by sorting IDs"""
    # Convert to integers and sort
    ids = sorted([int(doctor_id), int(patient_id)])
    return f"chat_{ids[0]}_{ids[1]}"


@socketio.on('join_room')
def handle_join(data):
    """User joins a chat room - FIXED VERSION"""
    try:
        room = data.get("room")
        user_id = data.get("user_id")
        
        if not room:
            # Create room based on doctor-patient if not provided
            doctor_id = data.get("doctor_id")
            patient_id = data.get("patient_id")
            if doctor_id and patient_id:
                # Use the sorted room creation function
                room = create_room_name(doctor_id, patient_id)
            else:
                print(f"❌ Cannot determine room for user {user_id}")
                return

        # Join the room
        join_room(room)

        # Track user in room
        if room not in active_users_by_room:
            active_users_by_room[room] = []

        user_info = {
            'sid': request.sid,
            'user_id': user_id,
            'joined_at': datetime.utcnow().isoformat()
        }

        # Prevent duplicates
        existing_user = next((u for u in active_users_by_room[room] if u['user_id'] == user_id), None)
        if not existing_user:
            active_users_by_room[room].append(user_info)

        print(f"✅ USER JOINED ROOM")
        print(f"   Room: {room}")
        print(f"   User ID: {user_id}")
        print(f"   Socket ID: {request.sid}")
        print(f"   Current rooms for this socket: {rooms()}")
        print(f"   Total users in room {room}: {len(active_users_by_room[room])}")
        print(f"   Users in room: {[u['user_id'] for u in active_users_by_room[room]]}")

        # Send confirmation
        emit('join_confirmation', {
            'room': room,
            'user_id': user_id,
            'message': f'Successfully joined room {room}',
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        print(f"❌ Error in handle_join: {str(e)}")
        import traceback
        traceback.print_exc()


@socketio.on("send_message")
def handle_send_message(data):
    """
    DEBUG VERSION - Track message flow with DB debugging
    """
    try:
        room = data.get("room")
        message_text = data.get("message", "").strip()
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")

        print("\n" + "="*60)
        print("📨 MESSAGE RECEIVED FROM SOCKET")
        print(f"   Room: {room}")
        print(f"   Sender ID: {sender_id}")
        print(f"   Receiver ID: {receiver_id}")
        print(f"   Message: '{message_text}'")
        
        if not room or not message_text:
            print("❌ Missing room or message")
            return {'error': 'Missing room or message'}

        print("   🔍 Attempting to save to database...")
        
        # Create message object
        new_message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message_text,
            timestamp=datetime.utcnow()
        )
        
        print(f"   Created Message object:")
        print(f"      sender_id: {new_message.sender_id}")
        print(f"      receiver_id: {new_message.receiver_id}")
        print(f"      message: '{new_message.message}'")
        
        # Add to session
        db.session.add(new_message)
        print("   ✅ Added to session")
        
        # Try to flush to get the ID
        try:
            db.session.flush()
            print(f"   ✅ Flushed - Message ID would be: {new_message.id}")
        except Exception as flush_error:
            print(f"   ❌ Flush failed: {flush_error}")
            import traceback
            traceback.print_exc()
        
        # Commit to database
        try:
            db.session.commit()
            print(f"   ✅ COMMITTED to database - Message ID: {new_message.id}")
        except Exception as commit_error:
            print(f"   ❌ Commit failed: {commit_error}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return {'error': f'Database error: {str(commit_error)}'}

        # Prepare message data for broadcasting
        message_data = {
            "message": message_text,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "timestamp": new_message.timestamp.replace(
                tzinfo=pytz.utc
            ).astimezone(IST).isoformat(),
            "message_id": new_message.id,
            "room": room
        }

        print(f"   📤 BROADCASTING TO ROOM: {room}")
        
        # Broadcast to room
        emit("new_message", message_data, room=room)
        
        print("   ✅ Message broadcast complete")
        print("="*60 + "\n")

        return {
            'status': 'success',
            'message_id': new_message.id,
            'broadcasted': True
        }

    except Exception as e:
        print(f"❌ Error in handle_send_message: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return {'error': str(e)}

@socketio.on('leave_room')
def handle_leave(data):
    room = data.get("room")
    user_id = data.get("user_id", "unknown")

    if room and room in active_users_by_room:
        # Remove this socket from room
        active_users_by_room[room] = [
            u for u in active_users_by_room[room]
            if u['sid'] != request.sid
        ]

        # Remove empty room entry
        if not active_users_by_room[room]:
            del active_users_by_room[room]

        print(f"👋 User {user_id} left room: {room}")
        print(f"   Remaining users in room: {len(active_users_by_room.get(room, []))}")


@socketio.on('connect')
def handle_connect():
    print("\n🔌 NEW CONNECTION ESTABLISHED")
    print(f"   Socket ID: {request.sid}")
    print(f"   Headers: {dict(request.headers)}")

    if current_user.is_authenticated:
        print(f"   Authenticated user: {current_user.username} (ID: {current_user.id})")
    else:
        print("   Anonymous connection")

    emit('connection_confirmed', {
        'sid': request.sid,
        'message': 'Connected to chat server',
        'timestamp': datetime.utcnow().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print("\n🔌 CONNECTION LOST")
    print(f"   Socket ID: {sid}")

    # Remove from all rooms
    for room, users in list(active_users_by_room.items()):
        active_users_by_room[room] = [
            u for u in users if u['sid'] != sid
        ]
        if not active_users_by_room[room]:
            del active_users_by_room[room]
            print(f"   Room '{room}' removed (empty)")


@socketio.on('debug_rooms')
def handle_debug_rooms(data):
    print("\n🔍 DEBUG ROOM STATUS")
    print(f"   All active rooms: {list(active_users_by_room.keys())}")

    for room, users in active_users_by_room.items():
        print(f"   Room {room}: {len(users)} users")
        for user in users:
            print(f"      - User ID: {user['user_id']}, SID: {user['sid'][:10]}...")


@socketio.on('ping_test')
def handle_ping(data):
    """Test Socket.IO connectivity"""
    emit('pong_response', {
        'message': 'Pong!',
        'timestamp': datetime.utcnow().isoformat(),
        'received_data': data
    })
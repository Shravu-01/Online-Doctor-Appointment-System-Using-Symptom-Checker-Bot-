# messaging.py
from proj.models import Message, db
from sqlalchemy import or_, and_

def store_message(sender_id, receiver_id, message):
    new_message = Message(sender_id=sender_id, receiver_id=receiver_id, message=message)
    db.session.add(new_message)
    db.session.commit()
    return new_message

def get_messages_between_users(user1_id, user2_id):
    # Fix the filter condition - use proper SQLAlchemy syntax
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == user1_id, Message.receiver_id == user2_id),
            and_(Message.sender_id == user2_id, Message.receiver_id == user1_id)
        )
    ).order_by(Message.timestamp.asc()).all()  # Use asc() for chronological order
    
    print(f"🔍 Database query: Found {len(messages)} messages between User {user1_id} and User {user2_id}")
    
    # Debug: Print each message found
    for msg in messages:
        print(f"   - Message ID: {msg.id}, From: {msg.sender_id}, To: {msg.receiver_id}, Time: {msg.timestamp}")
    
    return messages
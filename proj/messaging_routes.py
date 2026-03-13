# messaging_routes.py
#Do Not Run Directly
#Run using cmd through the project directory 
#python -m proj.messaging_routes (Run in bash)


from flask import Blueprint, request, jsonify
from proj import db
from proj.models import Message

messaging_blueprint = Blueprint('messaging', __name__)

@messaging_blueprint.route('/send_message', methods=['POST'])
def send_message():
    # Get the sender and receiver IDs from the request
    sender_id = request.json['sender_id']
    receiver_id = request.json['receiver_id']
    message = request.json['message']

    # Create a new message object
    new_message = Message(sender_id=sender_id, receiver_id=receiver_id, message=message)

    # Add the message to the database
    db.session.add(new_message)
    db.session.commit()

    return jsonify({'message': 'Message sent successfully'}), 200

@messaging_blueprint.route('/get_messages', methods=['GET'])
def get_messages():
    # Get the sender and receiver IDs from the query parameters
    sender_id = request.args.get('sender_id')
    receiver_id = request.args.get('receiver_id')

    # Retrieve messages between the sender and receiver
    messages = Message.query.filter_by(sender_id=sender_id, receiver_id=receiver_id).all()
    messages += Message.query.filter_by(sender_id=receiver_id, receiver_id=sender_id).all()

    # Convert the messages to a list of dictionaries
    messages = [{'sender_id': message.sender_id, 'receiver_id': message.receiver_id, 'message': message.message} for message in messages]

    return jsonify({'messages': messages}), 200
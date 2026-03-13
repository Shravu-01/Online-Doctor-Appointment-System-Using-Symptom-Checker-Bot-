import sys
import os
import unittest
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from proj import create_app, db
from proj.models import User, Message

class TestUserAuthentication(unittest.TestCase):
    def setUp(self):
        # Create app with testing config
        self.app = create_app('testing')
        self.appctx = self.app.app_context()
        self.appctx.push()
        db.create_all()  # create tables in in-memory DB

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.appctx.pop()

    def test_valid_login(self):
        # Create a test user
        user = User(username='testuser', email='test@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # Test login with valid credentials
        with self.app.test_client() as client:
            response = client.post(
                '/login',
                data={'username': 'testuser', 'password': 'password'},
                follow_redirects=False
            )
            self.assertEqual(response.status_code, 302)  # redirect to dashboard

    def test_invalid_login(self):
        # Create a test user
        user = User(username='testuser', email='test@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # Test login with invalid credentials
        with self.app.test_client() as client:
            response = client.post(
                '/login',
                data={'username': 'testuser', 'password': 'wrongpassword'},
                follow_redirects=False
            )
            self.assertEqual(response.status_code, 302)  # redirect back to login

    def test_password_hashing(self):
        user = User(username='testuser', email='test@example.com')
        user.set_password('password')
        self.assertNotEqual(user.password_hash, 'password')

    def test_message_creation(self):
        # Create users
        sender = User(username='sender', email='sender@example.com')
        sender.set_password('pass1')
        receiver = User(username='receiver', email='receiver@example.com')
        receiver.set_password('pass2')

        db.session.add(sender)
        db.session.add(receiver)
        db.session.commit()

        # Create message
        msg = Message(sender_id=sender.id, receiver_id=receiver.id, message="Hello!")
        db.session.add(msg)
        db.session.commit()

        # Verify message
        stored_msg = Message.query.first()
        self.assertEqual(stored_msg.sender_id, sender.id)
        self.assertEqual(stored_msg.receiver_id, receiver.id)
        self.assertEqual(stored_msg.message, "Hello!")

if __name__ == '__main__':
    unittest.main()



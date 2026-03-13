#Do not run directly



import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail   # ✅ Added
from flask_socketio import SocketIO  # ✅ Added
from proj.login_manager import login_manager
from flask_migrate import Migrate

# Initialize extensions
db = SQLAlchemy()
mail = Mail()   # ✅ Added
socketio = SocketIO(cors_allowed_origins="*")  # ✅ Added SocketIO
migrate = Migrate() 

def create_app(config_name=None):
    app = Flask(__name__)

    # ✅ Explicitly set template folder path
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    app.template_folder = template_path
    
    print("👉 Using template folder:", app.template_folder)
    print("👉 Template folder exists:", os.path.exists(app.template_folder))


    # ✅ Default config
    app.config['SECRET_KEY'] = "supersecretkey123!@#delulu"
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:DelulU1848$@localhost/delulu1'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ✅ Mail config
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 465
    app.config["MAIL_USE_TLS"] = False
    app.config["MAIL_USE_SSL"] = True
    app.config["MAIL_USERNAME"] = "truehealhealthtech@gmail.com"       # ⚠️ replace with real email
    app.config["MAIL_PASSWORD"] = "hpaxnutwdgkdgimg"                    # ⚠️ replace with real APP PASSWORD

    # ✅ Testing config override
    if config_name == "testing":
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # in-memory DB for tests

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "info"

    mail.init_app(app)   # ✅ bind Mail to app
    socketio.init_app(app)  # ✅ bind SocketIO to app
    migrate.init_app(app, db)   # ✅ added

    # ✅ user loader callback
    from proj.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ✅ register blueprints
    from proj.routes import main
    app.register_blueprint(main)

    # ✅ register messaging blueprint
    from proj.messaging_routes import messaging_blueprint
    app.register_blueprint(messaging_blueprint, url_prefix="/messages")

    # ✅ import socket handlers so events are registered
    from proj import socket_handlers


    return app

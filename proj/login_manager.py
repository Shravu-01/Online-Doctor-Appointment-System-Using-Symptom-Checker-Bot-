
from flask import Flask
from flask_login import LoginManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'DelulU1848$' 
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main.login'

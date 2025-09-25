# --- IMPORTS INITIAUX ET CONFIGURATION FLASK ---
import os
import urllib.parse
from datetime import datetime, date, timedelta, time
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder='static', static_url_path='/static')

# -- Configuration de la base de données
database_url = os.environ.get('DATABASE_URL')
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'retouches.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['LANG'] = 'fr'


# -- Configuration des informations pour le ticket
app.config['PAULA_COUTURE_ADRESSE'] = "40 rue Basse du Château"
app.config['PAULA_COUTURE_VILLE'] = "73000 Chambéry"
app.config['PAULA_COUTURE_TEL'] = "04 79 68 85 84"
app.config['PAULA_COUTURE_EMAIL'] = "paula.couture@ymail.com"
app.config['PAULA_COUTURE_SIRET'] = "789 369 584"
app.config['TVA_RATE'] = 0.20 

# On lit les secrets depuis les variables d'environnement
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'remplacez-moi-par-une-cle-secrete-unique-et-longue'
app.config['TWILIO_ACCOUNT_SID'] = os.environ.get('TWILIO_ACCOUNT_SID')
app.config['TWILIO_AUTH_TOKEN'] = os.environ.get('TWILIO_AUTH_TOKEN')
app.config['TWILIO_PHONE_NUMBER'] = os.environ.get('TWILIO_PHONE_NUMBER')

# --- INITIALISATION DES EXTENSIONS ---
db = SQLAlchemy(app)
migrate = Migrate(app, db)
twilio_client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])

# --- CONTEXT PROCESSOR (pour rendre 'config' disponible dans tous les templates) ---
@app.context_processor
def inject_config():
    return dict(config=app.config)

# --- CONTEXT PROCESSOR pour rendre 'timedelta' disponible dans tous les templates ---
@app.context_processor
def inject_timedelta():
    return dict(timedelta=timedelta)

# --- IMPORT DES ROUTES ---
from mon_atelier import routes


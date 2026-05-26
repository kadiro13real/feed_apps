from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import time
import requests
import smtplib
import os
from email.message import EmailMessage


app = Flask(__name__)
app.secret_key = "supersecretkey"  # change this
URI_KEY = os.getenv("URI_KEY")
MAIL_PASS = os.getenv("MAIL_PASS")


# Aiven PostgreSQL connection string (IMPORTANT: use postgresql:// not postgres://)
app.config["SQLALCHEMY_DATABASE_URI"] = URI_KEY
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

page=""

def build_message(subject, sender, recipient, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)
    return msg

def send_email(msg):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("fishingwebsiteinfo@gmail.com", MAIL_PASS)
        smtp.send_message(msg)

db = SQLAlchemy(app)

# -------------------------
# User Model
# -------------------------
class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    if "user" in session:
        return redirect("/welcome")
    else:
        return redirect("/login")

@app.route("/tournaments", methods=["GET", "POST"])
def tournaments():
    
    if "user" in session:
        
        return render_template("tournaments.html", user=session['user'])
    else:
        session["next"] = "/tournaments"
        return redirect("/login")

@app.route("/fish_map", methods=["GET", "POST"])
def fish_map():
    
    if "user" in session:
        
        return render_template("map.html", user=session['user'])
    else:
        session["next"] = "/fish_map"
        return redirect("/login")

@app.route("/report", methods=["GET", "POST"])
def report():
    
    if "user" in session:
        
        return render_template("report.html", user=session['user'])
    else:
        session["next"] = "/report"
        return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]

        # Check if username already exists
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            return "Username already taken"
        existing_email = Users.query.filter_by(email=email).first()
        if existing_email:
            return "email already taken"

        hashed = generate_password_hash(password)

        new_user = Users(username=username, password=hashed, email=email)
        db.session.add(new_user)
        db.session.commit()
        email = build_message(
            "FISHING FEED ACCOUNT",
            "fishingwebsiteinfo@gmail.com",
            email,
            f"Thank You For making a fishing feed account {username}"
            )
        send_email(email)

        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.pop("user", None)

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = Users.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user"] = user.username
            print(session.get("next", "/welcome"))
            return redirect(session.get("next", "/welcome"))

        return "Invalid username or password"

    return render_template("login.html")

@app.route("/welcome")
def welcome():
    if "user" not in session:
        return redirect("/login")
    return render_template("welcome.html", user=session['user'])

# -------------------------
# Render Keep-Alive Thread
# -------------------------
def keep_alive():
    while True:
        try:
            requests.get("https://YOUR-RENDER-URL.onrender.com")
        except:
            pass
        time.sleep(600)  # ping every 10 minutes

threading.Thread(target=keep_alive, daemon=True).start()

# -------------------------
# Run App
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

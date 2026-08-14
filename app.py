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
class Users2(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)

    friends = db.relationship(
        'Users2',
        secondary=friends,
        primaryjoin=id == friends.c.user_id,
        secondaryjoin=id == friends.c.friend_id,
        backref='friend_of'
    )

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20))  # pending, accepted, rejected

    from_user = db.relationship('Users2', foreign_keys=[from_id])
    to_user = db.relationship('Users2', foreign_keys=[to_id])




def send_friend_request(from_user, to_user):
    # cannot friend yourself
    if from_user.id == to_user.id:
        return "You cannot friend yourself"

    # already friends?
    if to_user in from_user.friends:
        return "Already friends"

    # existing pending request?
    existing = FriendRequest.query.filter_by(
        from_id=from_user.id,
        to_id=to_user.id,
        status="pending"
    ).first()

    if existing:
        return "Request already sent"

    # create new request
    req = FriendRequest(from_id=from_user.id, to_id=to_user.id, status="pending")
    db.session.add(req)
    db.session.commit()
    return "Friend request sent"

def accept_friend_request(request_id):
    req = FriendRequest.query.get(request_id)
    if not req or req.status != "pending":
        return "Invalid request"

    user = req.from_user
    friend = req.to_user

    # mutual friendship
    user.friends.append(friend)
    friend.friends.append(user)

    req.status = "accepted"
    db.session.commit()
    return "Friend request accepted"

def reject_friend_request(request_id):
    req = FriendRequest.query.get(request_id)
    if not req or req.status != "pending":
        return "Invalid request"

    req.status = "rejected"
    db.session.commit()
    return "Friend request rejected"

def get_received_requests(user):
    return FriendRequest.query.filter_by(
        to_id=user.id,
        status="pending"
    ).all()




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
        existing_user = Users2.query.filter_by(username=username).first()
        if existing_user:
            return "Username already taken"
        existing_email = Users2.query.filter_by(email=email).first()
        if existing_email:
            return "email already taken"

        hashed = generate_password_hash(password)

        new_user = Users2(username=username, password=hashed, email=email)
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

        user = Users2.query.filter_by(username=username).first()

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

@app.route("/friend_requests")
def friend_requests():
    if "user" not in session:
        return redirect("/login")
    user = session['user']
    received = get_received_requests(user)
    return render_template("friend_requests.html", requests=received)

@app.route("/send_request/<int:to_id>")
def send_request(to_id):
    from_user = current_user
    to_user = Users.query.get(to_id)
    return send_friend_request(from_user, to_user)

@app.route("/accept_request/<int:req_id>")
def accept_request(req_id):
    return accept_friend_request(req_id)

@app.route("/reject_request/<int:req_id>")
def reject_request(req_id):
    return reject_friend_request(req_id)


# -------------------------
# Render Keep-Alive Thread
# -------------------------
def keep_alive():
    while True:
        try:
            requests.get("https://feed-apps.onrender.com/")
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

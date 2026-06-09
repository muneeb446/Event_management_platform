from flask import Flask, render_template, request, redirect, url_for, send_file, session, make_response, jsonify, flash
from database import get_connection, create_tables, create_new_tables
from werkzeug.utils import secure_filename
import qrcode
import os, uuid, tempfile, secrets, datetime, urllib.request, json as _json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "eventhub_super_secret_2026"

ADMIN_EMAIL    = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

create_tables()  # creates ALL tables including new features

for d in ["static/uploads","static/gallery","static/qr_codes","static/images"]:
    os.makedirs(d, exist_ok=True)

# ── SEED EVENTS ───────────────────────────────────────────────────────────────
conn = get_connection()
cur  = conn.cursor()
cur.execute("SELECT COUNT(*) FROM events")
if cur.fetchone()[0] == 0:
    cur.executemany(
        "INSERT INTO events(title,date,time,location,image,category,description,seats,fee) VALUES(?,?,?,?,?,?,?,?,?)",
        [
            ("AI Workshop",  "20 June 2026","10:00 AM","Auditorium","","Workshop","Hands-on AI/ML session with industry experts.",100,0),
            ("Hackathon",    "25 June 2026","09:00 AM","Lab Block", "","Technical","24-hour coding competition. Build innovative projects.",50,0),
            ("Music Fest",   "30 June 2026","06:00 PM","Open Stage","","Cultural","Annual music and cultural extravaganza.",200,0),
        ]
    )
    conn.commit()
conn.close()

# ── HELPERS ───────────────────────────────────────────────────────────────────
CATEGORY_IMAGES = {
    "Workshop":  "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=800&auto=format&fit=crop",
    "Technical": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800&auto=format&fit=crop",
    "Cultural":  "https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=800&auto=format&fit=crop",
    "Sports":    "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800&auto=format&fit=crop",
    "Seminar":   "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&auto=format&fit=crop",
    "default":   "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800&auto=format&fit=crop",
}

def event_image_url(event):
    img = (event["image"] or "").strip()
    if img:
        path = os.path.join("static","uploads",img)
        if os.path.exists(path):
            return url_for("static", filename="uploads/"+img)
    return CATEGORY_IMAGES.get(event["category"] or "default", CATEGORY_IMAGES["default"])

app.jinja_env.globals["event_image_url"] = event_image_url

def tmp_path(f): return os.path.join(tempfile.gettempdir(), f)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*a, **kw):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*a, **kw):
        if "admin" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return decorated

# ── HOME ──────────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def home():
    category = request.args.get("category","")
    search   = request.args.get("search","")
    conn = get_connection(); cur = conn.cursor()
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    if category:
        query += " AND category=?"; params.append(category)
    if search:
        query += " AND (title LIKE ? OR location LIKE ?)"; params += [f"%{search}%", f"%{search}%"]
    cur.execute(query, params)
    events = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM events");       total_events = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users");        total_users  = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM registrations"); total_regs  = cur.fetchone()[0]
    cur.execute("SELECT DISTINCT category FROM events")
    categories = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()
    return render_template("index.html", events=events, total_events=total_events,
        total_users=total_users, total_registrations=total_regs,
        categories=categories, selected_category=category, search=search)

# ── AUTH ──────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if "user" in session: return redirect(url_for("home"))
    remembered = request.cookies.get("remembered_email","")
    if request.method == "POST":
        identifier = request.form["email"]
        password   = request.form["password"]
        remember   = request.form.get("remember_me")
        if identifier == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["admin"] = True; session["user"] = "Admin"
            return redirect(url_for("admin"))
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE (LOWER(email)=LOWER(?) OR LOWER(name)=LOWER(?)) AND password=?",
                    (identifier, identifier, password))
        user = cur.fetchone(); conn.close()
        if user:
            session["user"]    = user["name"]
            session["user_id"] = user["id"]
            session["email"]   = user["email"]
            resp = make_response(redirect(url_for("home")))
            if remember: resp.set_cookie("remembered_email", identifier, max_age=30*24*3600)
            else:        resp.delete_cookie("remembered_email")
            return resp
        return render_template("login.html", error="Invalid username/email or password.", remembered_email=remembered)
    return render_template("login.html", remembered_email=remembered)

@app.route("/register", methods=["POST"])
def register():
    name    = request.form["name"]
    email   = request.form["email"]
    pw      = request.form["password"]
    confirm = request.form.get("confirm_password","")
    if pw != confirm:
        return render_template("login.html", error="Passwords do not match.")
    if len(pw) < 6:
        return render_template("login.html", error="Password must be at least 6 characters.")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=?", (email,))
    if cur.fetchone():
        conn.close()
        return render_template("login.html", error="Email already registered. Please log in.")
    cur.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)", (name,email,pw))
    conn.commit(); conn.close()
    return render_template("login.html", success="Account created! Please sign in.")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── FORGOT / RESET PASSWORD ────────────────────────────────────────────────────
@app.route("/forgot_password", methods=["POST"])
def forgot_password():
    email = request.form.get("forgot_email","").strip()
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=?", (email,))
    user = cur.fetchone()
    if user:
        token  = secrets.token_urlsafe(32)
        expiry = (datetime.datetime.utcnow()+datetime.timedelta(hours=1)).isoformat()
        cur.execute("UPDATE users SET reset_token=?, reset_token_expiry=? WHERE email=?", (token,expiry,email))
        conn.commit(); conn.close()
        return render_template("login.html",
            success=f"Reset link generated! Go to: /reset_password/{token}")
    conn.close()
    return render_template("login.html", error="Email not found.")

@app.route("/reset_password/<token>", methods=["GET","POST"])
def reset_password(token):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE reset_token=?", (token,))
    user = cur.fetchone()
    if not user:
        conn.close(); return render_template("login.html", error="Invalid or expired reset link.")
    if user["reset_token_expiry"] and datetime.datetime.utcnow() > datetime.datetime.fromisoformat(user["reset_token_expiry"]):
        conn.close(); return render_template("login.html", error="Reset link expired. Please request a new one.")
    if request.method == "POST":
        pw = request.form.get("password",""); cp = request.form.get("confirm","")
        if pw != cp:   return render_template("reset_password.html", token=token, error="Passwords do not match.")
        if len(pw)<6:  return render_template("reset_password.html", token=token, error="Password must be at least 6 characters.")
        cur.execute("UPDATE users SET password=?, reset_token=NULL, reset_token_expiry=NULL WHERE reset_token=?", (pw,token))
        conn.commit(); conn.close()
        return render_template("login.html", success="Password updated! Please sign in.")
    conn.close()
    return render_template("reset_password.html", token=token)

# ── USER PROFILE ──────────────────────────────────────────────────────────────
@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update":
            name  = request.form.get("name","").strip()
            phone = request.form.get("phone","").strip()
            college = request.form.get("college","").strip()
            degree  = request.form.get("degree","").strip()
            cur.execute("UPDATE users SET name=?, phone=?, college=?, degree=? WHERE id=?",
                        (name, phone, college, degree, uid))
            session["user"] = name
            conn.commit()
            flash("Profile updated successfully!", "success")
        elif action == "change_password":
            old = request.form.get("old_password","")
            new = request.form.get("new_password","")
            cnf = request.form.get("confirm_password","")
            cur.execute("SELECT password FROM users WHERE id=?", (uid,))
            row = cur.fetchone()
            if not row or row["password"] != old:
                flash("Current password is incorrect.", "error")
            elif new != cnf:
                flash("New passwords do not match.", "error")
            elif len(new) < 6:
                flash("Password must be at least 6 characters.", "error")
            else:
                cur.execute("UPDATE users SET password=? WHERE id=?", (new, uid))
                conn.commit()
                flash("Password changed successfully!", "success")
        conn.close()
        return redirect(url_for("profile"))
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    user = cur.fetchone()
    cur.execute("""SELECT registrations.*, events.title, events.date, events.category
                   FROM registrations JOIN events ON registrations.event_id=events.id
                   WHERE registrations.registered_by=? ORDER BY registrations.id DESC""", (session["user"],))
    my_regs = cur.fetchall()
    conn.close()
    return render_template("profile.html", user=user, my_regs=my_regs)

# ── EVENTS ────────────────────────────────────────────────────────────────────
@app.route("/event/<int:event_id>")
@login_required
def event_details(event_id):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=?", (event_id,))
    event = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM registrations WHERE event_id=?", (event_id,))
    reg_count = cur.fetchone()[0]
    cur.execute("""SELECT f.*, u.name as uname FROM feedback f
                   LEFT JOIN users u ON f.user_name=u.name
                   WHERE f.event_id=? ORDER BY f.id DESC""", (event_id,))
    reviews = cur.fetchall()
    cur.execute("SELECT * FROM comments WHERE event_id=? ORDER BY id DESC", (event_id,))
    comments = cur.fetchall()
    # Check if current user already registered
    cur.execute("SELECT id FROM registrations WHERE event_id=? AND registered_by=?",
                (event_id, session.get("user","")))
    existing_reg = cur.fetchone()
    reg_id = existing_reg["id"] if existing_reg else None
    conn.close()
    if not event: return "Event not found", 404
    return render_template("event_details.html", event=event, reg_count=reg_count,
                           reviews=reviews, comments=comments, reg_id=reg_id)

@app.route("/register_event/<int:event_id>", methods=["GET","POST"])
@login_required
def register_event(event_id):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=?", (event_id,))
    event = cur.fetchone(); conn.close()
    if not event: return "Event not found", 404
    if request.method == "POST":
        session["pending_reg"] = {
            "event_id": event_id,
            "name":    request.form["name"],
            "age":     request.form["age"],
            "college": request.form["college"],
            "degree":  request.form["degree"],
            "phone":   request.form.get("phone",""),
        }
        return redirect(url_for("payment", event_id=event_id))
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (session.get("user_id"),))
    user = cur.fetchone(); conn.close()
    return render_template("register_event.html", event=event, user=user)

@app.route("/payment/<int:event_id>", methods=["GET","POST"])
@login_required
def payment(event_id):
    pending = session.get("pending_reg")
    if not pending or pending.get("event_id") != event_id:
        return redirect(url_for("register_event", event_id=event_id))
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=?", (event_id,))
    event = cur.fetchone(); conn.close()
    if not event: return "Event not found", 404
    if request.method == "POST":
        method = request.form.get("payment_method","Free")
        registered_by = session.get("user","guest")
        conn = get_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO registrations(event_id,user_name,age,college,degree,phone,registered_by) VALUES(?,?,?,?,?,?,?)",
            (pending["event_id"], pending["name"], pending["age"],
             pending["college"], pending["degree"], pending.get("phone",""), registered_by))
        conn.commit(); reg_id = cur.lastrowid; conn.close()
        qr_data = f"EventHub Ticket\nID:EVT{reg_id}\nName:{pending['name']}\nEvent:{event['title']}\nDate:{event['date']}\nLocation:{event['location']}"
        qr_img = qrcode.make(qr_data)
        safe = secure_filename(pending["name"])
        qr_fn = f"{safe}_{reg_id}.png"
        qr_img.save(os.path.join("static","qr_codes",qr_fn))
        session.pop("pending_reg", None)
        return render_template("ticket.html", name=pending["name"], college=pending["college"],
            degree=pending["degree"], age=pending["age"], event=event, qr_filename=qr_fn,
            safe_name=safe, reg_id=reg_id, payment_method=method)
    return render_template("payment.html", event=event, pending=pending)

# ── MY REGISTRATIONS ──────────────────────────────────────────────────────────
@app.route("/my_registrations")
@login_required
def my_registrations():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT r.*, e.title, e.image, e.date, e.location, e.category, e.time
                   FROM registrations r JOIN events e ON r.event_id=e.id
                   WHERE r.registered_by=? ORDER BY r.id DESC""", (session["user"],))
    regs = cur.fetchall(); conn.close()
    return render_template("my_registrations.html", registrations=regs)

# ── DOWNLOAD TICKET PDF ───────────────────────────────────────────────────────
@app.route("/download_ticket/<name>/<int:reg_id>")
@login_required
def download_ticket(name, reg_id):
    safe = secure_filename(name)
    path = tmp_path(f"{safe}_{reg_id}_ticket.pdf")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT r.*, e.title, e.date, e.location, e.time, e.category
                   FROM registrations r JOIN events e ON r.event_id=e.id WHERE r.id=?""", (reg_id,))
    reg = cur.fetchone(); conn.close()
    c = canvas.Canvas(path, pagesize=letter); W,H = letter
    c.setFillColor(colors.HexColor("#0f172a")); c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(colors.HexColor("#6c23c8")); c.rect(0,H-120,W,120,fill=1,stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold",30)
    c.drawCentredString(W/2,H-55,"EVENT TICKET")
    c.setFont("Helvetica",12); c.drawCentredString(W/2,H-80,"EventHub — College Event Management Platform")
    c.setFont("Helvetica-Bold",13); c.drawCentredString(W/2,H-105,f"Ticket ID: EVT{reg_id}")
    c.setFillColor(colors.white); c.roundRect(35,60,W-70,H-195,15,fill=1,stroke=0)
    c.setFillColor(colors.HexColor("#1e293b")); c.setFont("Helvetica-Bold",20)
    c.drawCentredString(W/2,H-160, reg["title"] if reg else name)
    c.setStrokeColor(colors.HexColor("#e2e8f0")); c.setLineWidth(1); c.setDash(4,4)
    c.line(55,H-180,W-55,H-180); c.setDash()
    details = [("Participant",reg["user_name"] if reg else name),("College",reg["college"] if reg else "—"),
               ("Degree",reg["degree"] if reg else "—"),("Date",reg["date"] if reg else "—"),
               ("Time",reg["time"] if reg else "—"),("Location",reg["location"] if reg else "—"),
               ("Category",reg["category"] if reg else "—")]
    y = H-215
    for label,value in details:
        c.setFillColor(colors.HexColor("#f1f5f9")); c.roundRect(55,y-8,155,24,5,fill=1,stroke=0)
        c.setFillColor(colors.HexColor("#6c23c8")); c.setFont("Helvetica-Bold",11); c.drawString(62,y+4,label)
        c.setFillColor(colors.HexColor("#1e293b")); c.setFont("Helvetica",12); c.drawString(225,y+4,str(value))
        y -= 33
    c.setStrokeColor(colors.HexColor("#e2e8f0")); c.setDash(4,4); c.line(55,215,W-55,215); c.setDash()
    qr_path = os.path.join("static","qr_codes",f"{safe}_{reg_id}.png")
    if os.path.exists(qr_path): c.drawImage(qr_path,W/2-65,75,width=130,height=130)
    c.setFillColor(colors.HexColor("#64748b")); c.setFont("Helvetica",9)
    c.drawCentredString(W/2,65,"Scan QR code at event entrance for verification")
    c.save()
    return send_file(path, as_attachment=True, download_name=f"EventHub_Ticket_EVT{reg_id}.pdf")

# ── DOWNLOAD CERTIFICATE PDF ──────────────────────────────────────────────────
@app.route("/download_certificate/<name>/<int:reg_id>")
@login_required
def download_certificate(name, reg_id):
    safe = secure_filename(name)
    path = tmp_path(f"{safe}_{reg_id}_cert.pdf")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT r.*, e.title, e.date, e.location, e.category, e.time
                   FROM registrations r JOIN events e ON r.event_id=e.id WHERE r.id=?""", (reg_id,))
    reg = cur.fetchone(); conn.close()
    c = canvas.Canvas(path, pagesize=A4); W,H = A4
    c.setFillColor(colors.HexColor("#fffef5")); c.rect(0,0,W,H,fill=1,stroke=0)
    c.setStrokeColor(colors.HexColor("#b8860b")); c.setLineWidth(6); c.rect(18,18,W-36,H-36,fill=0,stroke=1)
    c.setStrokeColor(colors.HexColor("#d4a017")); c.setLineWidth(2); c.rect(26,26,W-52,H-52,fill=0,stroke=1)
    c.setFillColor(colors.HexColor("#1a0533")); c.rect(18,H-100,W-36,82,fill=1,stroke=0)
    c.setFillColor(colors.HexColor("#d4a017")); c.setFont("Helvetica-Bold",11)
    c.drawCentredString(W/2,H-50,"E V E N T H U B")
    c.setFillColor(colors.white); c.setFont("Helvetica",10)
    c.drawCentredString(W/2,H-68,"College Event Management Platform")
    c.setFillColor(colors.HexColor("#1a0533")); c.setFont("Helvetica-Bold",36)
    c.drawCentredString(W/2,H-155,"Certificate of Participation")
    c.setStrokeColor(colors.HexColor("#d4a017")); c.setLineWidth(2); c.line(60,H-170,W-60,H-170)
    c.setFillColor(colors.HexColor("#333333")); c.setFont("Helvetica",14)
    c.drawCentredString(W/2,H-210,"This is to proudly certify that")
    participant = reg["user_name"] if reg else name
    c.setFillColor(colors.HexColor("#1a0533")); c.setFont("Helvetica-Bold",34)
    c.drawCentredString(W/2,H-260,participant)
    nw = c.stringWidth(participant,"Helvetica-Bold",34)
    c.setStrokeColor(colors.HexColor("#6c23c8")); c.setLineWidth(1.5)
    c.line(W/2-nw/2,H-270,W/2+nw/2,H-270)
    c.setFillColor(colors.HexColor("#333333")); c.setFont("Helvetica",14)
    c.drawCentredString(W/2,H-305,"has successfully participated in")
    c.setFillColor(colors.HexColor("#6c23c8")); c.setFont("Helvetica-Bold",22)
    c.drawCentredString(W/2,H-338, reg["title"] if reg else "the Event")
    c.setFillColor(colors.HexColor("#555555")); c.setFont("Helvetica",13)
    c.drawCentredString(W/2,H-362,f"Category: {reg['category'] if reg else ''} | Date: {reg['date'] if reg else ''} | Venue: {reg['location'] if reg else ''}")
    c.setFillColor(colors.HexColor("#f5f0ff")); c.roundRect(60,H-440,W-120,60,8,fill=1,stroke=0)
    c.setFillColor(colors.HexColor("#1a0533")); c.setFont("Helvetica-Bold",12)
    c.drawCentredString(W/2,H-410,f"{reg['college'] if reg else ''} — {reg['degree'] if reg else ''}")
    c.setFont("Helvetica",11); c.setFillColor(colors.HexColor("#64748b"))
    c.drawCentredString(W/2,H-430,f"Certificate ID: CERT-EVT{reg_id}-2026")
    c.setStrokeColor(colors.HexColor("#d4a017")); c.setLineWidth(1.5); c.line(60,H-455,W-60,H-455)
    for x,lbl in [(W/4,"Event Coordinator"),(3*W/4,"Principal / Director")]:
        c.setFillColor(colors.HexColor("#1a0533")); c.setFont("Helvetica-Bold",11)
        c.drawCentredString(x,100,lbl)
        c.setStrokeColor(colors.HexColor("#1a0533")); c.setLineWidth(1)
        c.line(x-70,85,x+70,85)
        c.setFont("Helvetica",10); c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(x,72,"Signature")
    c.setFillColor(colors.HexColor("#1a0533")); c.rect(18,18,W-36,50,fill=1,stroke=0)
    c.setFillColor(colors.HexColor("#d4a017")); c.setFont("Helvetica-Bold",10)
    c.drawCentredString(W/2,48,"EventHub — College Event Management Platform — 2026")
    c.save()
    return send_file(path, as_attachment=True, download_name=f"EventHub_Certificate_EVT{reg_id}.pdf")

# ── FEEDBACK ──────────────────────────────────────────────────────────────────
@app.route("/feedback", methods=["GET","POST"])
@login_required
def feedback():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, title FROM events"); events = cur.fetchall(); conn.close()
    if request.method == "POST":
        conn = get_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO feedback(event_id,user_name,rating,message) VALUES(?,?,?,?)",
            (request.form.get("event_id"), request.form.get("name",""),
             request.form.get("rating",""), request.form.get("message","")))
        conn.commit(); conn.close()
        return render_template("feedback_success.html", name=request.form.get("name",""))
    return render_template("feedback.html", events=events)

# ── GALLERY ───────────────────────────────────────────────────────────────────
@app.route("/gallery")
@login_required
def gallery():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM events"); events = cur.fetchall(); conn.close()
    all_files = set(os.listdir("static/gallery"))
    gallery_data = {}
    for ev in events:
        prefix = secure_filename(ev["title"]).lower()
        gallery_data[ev["title"]] = [f for f in all_files if f.lower().startswith(prefix+"_")]
    return render_template("gallery.html", events=events, gallery_data=gallery_data)

@app.route("/upload_gallery", methods=["POST"])
@admin_required
def upload_gallery():
    image = request.files.get("image"); event_name = request.form.get("event_name","other")
    if image and image.filename:
        fn = f"{secure_filename(event_name).lower()}_{uuid.uuid4().hex[:8]}_{secure_filename(image.filename)}"
        image.save(os.path.join("static/gallery",fn))
    return redirect(url_for("gallery"))

# ── ADMIN ─────────────────────────────────────────────────────────────────────
@app.route("/admin")
@admin_required
def admin():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM events ORDER BY id DESC");   events = cur.fetchall()
    cur.execute("""SELECT r.*, e.title, e.image, e.category FROM registrations r
                   JOIN events e ON r.event_id=e.id ORDER BY r.id DESC"""); regs = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM events");        te = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users");         tu = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM registrations"); tr = cur.fetchone()[0]
    cur.execute("SELECT * FROM feedback ORDER BY id DESC"); feedbacks = cur.fetchall()
    cur.execute("SELECT id, name, email FROM users ORDER BY id DESC"); users = cur.fetchall()
    cur.execute("SELECT * FROM announcements ORDER BY id DESC"); announcements = cur.fetchall()
    cur.execute("SELECT * FROM contact_messages ORDER BY id DESC"); contact_messages = cur.fetchall()
    conn.close()
    return render_template("admin.html", events=events, registrations=regs,
        total_events=te, total_users=tu, total_registrations=tr,
        feedbacks=feedbacks, users=users, announcements=announcements,
        contact_messages=contact_messages)

@app.route("/add_event", methods=["POST"])
@admin_required
def add_event():
    image = request.files.get("image"); image_name = ""
    if image and image.filename:
        unique_name = str(uuid.uuid4())+"_"+secure_filename(image.filename)
        image.save(os.path.join("static/uploads",unique_name)); image_name = unique_name
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO events(title,date,time,location,image,category,description,seats,fee) VALUES(?,?,?,?,?,?,?,?,?)",
        (request.form.get("title"), request.form.get("date"), request.form.get("time"),
         request.form.get("location"), image_name, request.form.get("category"),
         request.form.get("description",""), request.form.get("seats",0), request.form.get("fee",0)))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/edit_event/<int:eid>", methods=["GET","POST"])
@admin_required
def edit_event(eid):
    conn = get_connection(); cur = conn.cursor()
    if request.method == "POST":
        cur.execute("SELECT image FROM events WHERE id=?", (eid,)); row = cur.fetchone()
        image_name = row["image"] if row else ""
        image = request.files.get("image")
        if image and image.filename:
            unique_name = str(uuid.uuid4())+"_"+secure_filename(image.filename)
            image.save(os.path.join("static/uploads",unique_name)); image_name = unique_name
        cur.execute("UPDATE events SET title=?,date=?,time=?,location=?,image=?,category=?,description=?,seats=?,fee=? WHERE id=?",
            (request.form.get("title"), request.form.get("date"), request.form.get("time"),
             request.form.get("location"), image_name, request.form.get("category"),
             request.form.get("description",""), request.form.get("seats",0),
             request.form.get("fee",0), eid))
        conn.commit(); conn.close(); return redirect(url_for("admin"))
    cur.execute("SELECT * FROM events WHERE id=?", (eid,)); event = cur.fetchone(); conn.close()
    return render_template("edit_event.html", event=event)

@app.route("/delete_event/<int:eid>")
@admin_required
def delete_event(eid):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM events WHERE id=?", (eid,)); conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/delete_user/<int:uid>")
@admin_required
def delete_user(uid):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", (uid,)); conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/delete_registration/<int:rid>")
@admin_required
def delete_registration(rid):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM registrations WHERE id=?", (rid,)); conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/delete_feedback/<int:fid>")
@admin_required
def delete_feedback(fid):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM feedback WHERE id=?", (fid,)); conn.commit(); conn.close()
    return redirect(url_for("admin"))

# ── AI CHATBOT ────────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@login_required
def chat_api():
    data = request.get_json()
    # Option 1: Set ANTHROPIC_API_KEY environment variable (recommended)
    # Option 2: Replace "" below with your key directly e.g. "sk-ant-xxxx"
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    payload = _json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "system": data.get("system",""),
        "messages": data.get("messages",[])
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload,
        headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,
                 "anthropic-version":"2023-06-01"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read())
        return jsonify({"reply": result["content"][0]["text"]})
    except:
        return jsonify({"reply": "Sorry, I couldn't respond right now."}), 500

# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────
@app.route("/notifications")
@login_required
def notifications():
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC", (uid,))
    notifs = cur.fetchall()
    cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
    conn.commit(); conn.close()
    return render_template("notifications.html", notifs=notifs)

@app.route("/notifications/count")
@login_required
def notif_count():
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (uid,))
    count = cur.fetchone()[0]; conn.close()
    return jsonify({"count": count})

def add_notification(user_id, message, notif_type="info"):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO notifications(user_id,message,type,created_at) VALUES(?,?,?,?)",
        (user_id, message, notif_type, datetime.datetime.now().strftime("%d %b %Y %I:%M %p")))
    conn.commit(); conn.close()

# ── LEADERBOARD ───────────────────────────────────────────────────────────────
@app.route("/leaderboard")
@login_required
def leaderboard():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT registered_by, COUNT(*) as total
                   FROM registrations WHERE registered_by IS NOT NULL AND registered_by != ''
                   GROUP BY registered_by ORDER BY total DESC LIMIT 20""")
    leaders = cur.fetchall()
    cur.execute("""SELECT registered_by, COUNT(DISTINCT event_id) as events
                   FROM registrations WHERE registered_by IS NOT NULL
                   GROUP BY registered_by ORDER BY events DESC LIMIT 20""")
    event_leaders = cur.fetchall()
    my_name = session.get("user","")
    cur.execute("SELECT COUNT(*) FROM registrations WHERE registered_by=?", (my_name,))
    my_total = cur.fetchone()[0]
    cur.execute("""SELECT COUNT(*) FROM (
                   SELECT registered_by, COUNT(*) as c FROM registrations
                   WHERE registered_by IS NOT NULL GROUP BY registered_by
                   HAVING c > ?) """, (my_total,))
    my_rank = cur.fetchone()[0] + 1
    conn.close()
    return render_template("leaderboard.html", leaders=leaders,
        event_leaders=event_leaders, my_rank=my_rank, my_total=my_total)

# ── ANNOUNCEMENTS ─────────────────────────────────────────────────────────────
@app.route("/announcements")
@login_required
def announcements():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM announcements ORDER BY id DESC")
    items = cur.fetchall(); conn.close()
    return render_template("announcements.html", items=items)

@app.route("/admin/announcement", methods=["POST"])
@admin_required
def add_announcement():
    title   = request.form.get("title","")
    message = request.form.get("message","")
    priority = request.form.get("priority","normal")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO announcements(title,message,priority,created_at) VALUES(?,?,?,?)",
        (title, message, priority, datetime.datetime.now().strftime("%d %b %Y %I:%M %p")))
    ann_id = cur.lastrowid
    # notify all users
    cur.execute("SELECT id FROM users")
    users = cur.fetchall()
    for u in users:
        cur.execute("INSERT INTO notifications(user_id,message,type,created_at) VALUES(?,?,?,?)",
            (u[0], f"📢 New announcement: {title}", "announcement",
             datetime.datetime.now().strftime("%d %b %Y %I:%M %p")))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/announcement/delete/<int:aid>")
@admin_required
def delete_announcement(aid):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM announcements WHERE id=?", (aid,)); conn.commit(); conn.close()
    return redirect(url_for("admin"))

# ── WISHLIST / BOOKMARKS ──────────────────────────────────────────────────────
@app.route("/wishlist/toggle/<int:event_id>", methods=["POST"])
@login_required
def toggle_wishlist(event_id):
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM wishlist WHERE user_id=? AND event_id=?", (uid, event_id))
    existing = cur.fetchone()
    if existing:
        cur.execute("DELETE FROM wishlist WHERE user_id=? AND event_id=?", (uid, event_id))
        saved = False
    else:
        cur.execute("INSERT INTO wishlist(user_id,event_id) VALUES(?,?)", (uid, event_id))
        saved = True
    conn.commit(); conn.close()
    return jsonify({"saved": saved})

@app.route("/wishlist")
@login_required
def wishlist():
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT e.* FROM events e
                   JOIN wishlist w ON e.id=w.event_id
                   WHERE w.user_id=? ORDER BY w.id DESC""", (uid,))
    events = cur.fetchall(); conn.close()
    return render_template("wishlist.html", events=events)

@app.route("/wishlist/ids")
@login_required
def wishlist_ids():
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT event_id FROM wishlist WHERE user_id=?", (uid,))
    ids = [r[0] for r in cur.fetchall()]; conn.close()
    return jsonify({"ids": ids})

# ── EVENT SEARCH API (live) ───────────────────────────────────────────────────
@app.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q","").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT id,title,date,location,category FROM events
                   WHERE title LIKE ? OR location LIKE ? OR category LIKE ?
                   LIMIT 6""", (f"%{q}%", f"%{q}%", f"%{q}%"))
    results = [{"id":r[0],"title":r[1],"date":r[2],"location":r[3],"category":r[4]}
               for r in cur.fetchall()]
    conn.close()
    return jsonify({"results": results})

# ── ADMIN STATS API ───────────────────────────────────────────────────────────
@app.route("/api/admin/stats")
@admin_required
def admin_stats():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT category, COUNT(*) FROM events GROUP BY category")
    by_cat = dict(cur.fetchall())
    cur.execute("""SELECT e.title, COUNT(r.id) as cnt FROM events e
                   LEFT JOIN registrations r ON e.id=r.event_id
                   GROUP BY e.id ORDER BY cnt DESC LIMIT 5""")
    top_events = [{"title":r[0],"count":r[1]} for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) FROM users"); total_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM registrations"); total_regs = cur.fetchone()[0]
    conn.close()
    return jsonify({"by_category": by_cat, "top_events": top_events,
                    "total_users": total_users, "total_regs": total_regs})

# ── MARK ATTENDANCE (admin) ────────────────────────────────────────────────────
@app.route("/admin/attendance/<int:event_id>")
@admin_required
def attendance(event_id):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=?", (event_id,)); event = cur.fetchone()
    cur.execute("""SELECT r.* FROM registrations r WHERE r.event_id=?
                   ORDER BY r.user_name""", (event_id,))
    regs = cur.fetchall(); conn.close()
    return render_template("attendance.html", event=event, regs=regs)

@app.route("/admin/attendance/mark", methods=["POST"])
@admin_required
def mark_attendance():
    reg_id  = request.form.get("reg_id")
    present = request.form.get("present","0")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE registrations SET attended=? WHERE id=?", (present, reg_id))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# NEW FEATURES
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. EVENT REMINDER (user sets reminder for an event) ───────────────────────
@app.route("/reminder/set/<int:event_id>", methods=["POST"])
@login_required
def set_reminder(event_id):
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM reminders WHERE user_id=? AND event_id=?", (uid, event_id))
    if not cur.fetchone():
        cur.execute("INSERT INTO reminders(user_id,event_id,created_at) VALUES(?,?,?)",
            (uid, event_id, datetime.datetime.now().strftime("%d %b %Y %I:%M %p")))
        conn.commit()
        conn.close()
        return jsonify({"set": True, "msg": "Reminder set!"})
    else:
        cur.execute("DELETE FROM reminders WHERE user_id=? AND event_id=?", (uid, event_id))
        conn.commit()
        conn.close()
        return jsonify({"set": False, "msg": "Reminder removed"})

@app.route("/my_reminders")
@login_required
def my_reminders():
    uid = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT e.*, r.created_at as reminded_at FROM events e
                   JOIN reminders r ON e.id=r.event_id
                   WHERE r.user_id=? ORDER BY r.id DESC""", (uid,))
    events = cur.fetchall(); conn.close()
    return render_template("reminders.html", events=events)

# ── 2. EVENT COMMENTS ─────────────────────────────────────────────────────────
@app.route("/event/<int:event_id>/comment", methods=["POST"])
@login_required
def add_comment(event_id):
    text = request.form.get("comment","").strip()
    if not text:
        return redirect(url_for("event_details", event_id=event_id))
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO comments(event_id,user_name,comment,created_at) VALUES(?,?,?,?)",
        (event_id, session.get("user",""), text,
         datetime.datetime.now().strftime("%d %b %Y %I:%M %p")))
    conn.commit(); conn.close()
    return redirect(url_for("event_details", event_id=event_id))

@app.route("/comment/delete/<int:cid>")
@admin_required
def delete_comment(cid):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT event_id FROM comments WHERE id=?", (cid,))
    row = cur.fetchone()
    cur.execute("DELETE FROM comments WHERE id=?", (cid,))
    conn.commit(); conn.close()
    return redirect(url_for("event_details", event_id=row["event_id"] if row else 1))

# ── 3. ADMIN BROADCAST MESSAGE ────────────────────────────────────────────────
@app.route("/admin/broadcast", methods=["POST"])
@admin_required
def broadcast():
    msg = request.form.get("message","").strip()
    if msg:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT id FROM users")
        for u in cur.fetchall():
            cur.execute("INSERT INTO notifications(user_id,message,type,created_at) VALUES(?,?,?,?)",
                (u[0], f"📣 Admin: {msg}", "broadcast",
                 datetime.datetime.now().strftime("%d %b %Y %I:%M %p")))
        conn.commit(); conn.close()
    return redirect(url_for("admin"))

# ── 4. USER STATS PAGE ────────────────────────────────────────────────────────
@app.route("/my_stats")
@login_required
def my_stats():
    name = session.get("user","")
    uid  = session.get("user_id")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM registrations WHERE registered_by=?", (name,)); total_regs = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT event_id) FROM registrations WHERE registered_by=?", (name,)); unique_events = cur.fetchone()[0]
    cur.execute("""SELECT e.category, COUNT(*) as cnt FROM registrations r
                   JOIN events e ON r.event_id=e.id WHERE r.registered_by=?
                   GROUP BY e.category ORDER BY cnt DESC""", (name,)); by_cat = cur.fetchall()
    cur.execute("""SELECT r.*, e.title, e.date, e.category FROM registrations r
                   JOIN events e ON r.event_id=e.id WHERE r.registered_by=?
                   ORDER BY r.id DESC LIMIT 5""", (name,)); recent = cur.fetchall()
    cur.execute("""SELECT COUNT(*) FROM (SELECT registered_by, COUNT(*) as c
                   FROM registrations WHERE registered_by IS NOT NULL
                   GROUP BY registered_by HAVING c > ?)""", (total_regs,)); my_rank = cur.fetchone()[0]+1
    cur.execute("SELECT COUNT(*) FROM registrations WHERE registered_by=? AND attended=1", (name,)); attended = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM wishlist WHERE user_id=?", (uid,)); saved = cur.fetchone()[0]
    conn.close()
    return render_template("my_stats.html", total_regs=total_regs, unique_events=unique_events,
        by_cat=by_cat, recent=recent, my_rank=my_rank, attended=attended, saved=saved)

# ── 5. PRINT / SHARE TICKET PAGE ──────────────────────────────────────────────
@app.route("/view_ticket/<int:reg_id>")
@login_required
def view_ticket(reg_id):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT r.*, e.title, e.date, e.time, e.location, e.category
                   FROM registrations r JOIN events e ON r.event_id=e.id
                   WHERE r.id=?""", (reg_id,))
    reg = cur.fetchone(); conn.close()
    if not reg: return "Ticket not found", 404
    safe = secure_filename(reg["user_name"])
    qr_fn = f"{safe}_{reg_id}.png"
    return render_template("view_ticket.html", reg=reg, qr_fn=qr_fn)

# ── 6. DUPLICATE REGISTRATION CHECK ──────────────────────────────────────────
@app.route("/api/check_registration/<int:event_id>")
@login_required
def check_registration(event_id):
    name = session.get("user","")
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM registrations WHERE event_id=? AND registered_by=?", (event_id, name))
    existing = cur.fetchone(); conn.close()
    return jsonify({"already_registered": bool(existing),
                    "reg_id": existing["id"] if existing else None})

# ── 7. ADMIN EXPORT REGISTRATIONS CSV ────────────────────────────────────────
@app.route("/admin/export/<int:event_id>")
@admin_required
def export_csv(event_id):
    import csv, io
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT title FROM events WHERE id=?", (event_id,))
    ev = cur.fetchone()
    cur.execute("""SELECT r.id, r.user_name, r.age, r.college, r.degree, r.phone,
                   r.registered_by, r.attended, e.title, e.date
                   FROM registrations r JOIN events e ON r.event_id=e.id
                   WHERE r.event_id=?""", (event_id,))
    rows = cur.fetchall(); conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket ID","Name","Age","College","Degree","Phone","Registered By","Attended","Event","Date"])
    for r in rows:
        writer.writerow([f"EVT{r[0]}",r[1],r[2],r[3],r[4],r[5],r[6],"Yes" if r[7] else "No",r[8],r[9]])
    output.seek(0)
    fname = f"{secure_filename(ev['title'] if ev else 'event')}_registrations.csv"
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"})

@app.route("/admin/export_all")
@admin_required
def export_all_csv():
    import csv, io
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""SELECT r.id, r.user_name, r.age, r.college, r.degree, r.phone,
                   r.registered_by, r.attended, e.title, e.date, e.category
                   FROM registrations r JOIN events e ON r.event_id=e.id
                   ORDER BY r.id DESC""")
    rows = cur.fetchall(); conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket ID","Name","Age","College","Degree","Phone","Registered By","Attended","Event","Date","Category"])
    for r in rows:
        writer.writerow([f"EVT{r[0]}",r[1],r[2],r[3],r[4],r[5],r[6],"Yes" if r[7] else "No",r[8],r[9],r[10]])
    output.seek(0)
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=all_registrations.csv"})

# ── 8. CONTACT / HELP PAGE ────────────────────────────────────────────────────
@app.route("/help")
@login_required
def help_page():
    return render_template("help.html")

@app.route("/contact", methods=["POST"])
@login_required
def contact():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO contact_messages(name,email,subject,message,created_at) VALUES(?,?,?,?,?)",
        (request.form.get("name",""), request.form.get("email",""),
         request.form.get("subject",""), request.form.get("message",""),
         datetime.datetime.now().strftime("%d %b %Y %I:%M %p")))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── DB INIT ROUTE (run once after deploy) ────────────────────────────────────
@app.route("/init_db")
def init_db():
    try:
        create_tables()
        return "<h2 style='font-family:sans-serif;color:green;padding:40px'>✅ All tables created! You can close this page.</h2>"
    except Exception as e:
        return f"<h2 style='color:red;padding:40px'>❌ Error: {e}</h2>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

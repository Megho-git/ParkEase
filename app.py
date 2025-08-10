from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models.models import db, User, ParkingLot, ParkingSpot, Reservation
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
import math
from utils.utils import generate_qr_image, build_booking_email, send_email_with_qr
from dotenv import load_dotenv
import os
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)


# Database configuration - automatically chooses the right database
if os.environ.get('DATABASE_URL'):
    # Production (Render) - uses PostgreSQL  
    database_url = os.environ.get('DATABASE_URL')
    # Handle potential postgresql:// vs postgres:// URL difference
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Development (your computer) - uses SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
with app.app_context():
    try:
        # Create all tables if they don't exist
        db.create_all()
        
        # Create default admin if it doesn't exist
        if not User.query.filter_by(role='admin').first():
            from werkzeug.security import generate_password_hash
            hashed_pw = generate_password_hash("admin123")
            admin = User(
                email="admin@parkease.com",
                password=hashed_pw,
                fullname="Administrator", 
                address="Admin Office",
                pincode="000000",
                role="admin"
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created!")
    except Exception as e:
        print(f"Database initialization: {e}")
        
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash("Unauthorized access", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for('login'))
        if session.get('role') != 'user':
            flash("Unauthorized access", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/test-email-config')
def test_email_config():
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    
    return f"Email: {sender_email}, Password: {'Set' if sender_password else 'Not Set'}"
@app.route('/debug-env')
def debug_env():
    import os
    from pathlib import Path
    
    env_file = Path('.env')
    env_exists = env_file.exists()
    
    env_content = ""
    if env_exists:
        try:
            env_content = env_file.read_text()
        except:
            env_content = "Error reading file"
    
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    
    return f"""
    <h2>Environment Debug Info</h2>
    <p><strong>.env file exists:</strong> {env_exists}</p>
    <p><strong>Current working directory:</strong> {os.getcwd()}</p>
    <p><strong>.env file path:</strong> {env_file.absolute()}</p>
    <p><strong>SENDER_EMAIL:</strong> {sender_email}</p>
    <p><strong>SENDER_PASSWORD:</strong> {'*' * len(sender_password) if sender_password else 'None'}</p>
    <p><strong>SMTP_SERVER:</strong> {smtp_server}</p>
    <p><strong>SMTP_PORT:</strong> {smtp_port}</p>
    <hr>
    <h3>.env file content:</h3>
    <pre>{env_content}</pre>
    """
@app.route('/test-email-send')
def test_email_send():
    try:
        from utils.utils import send_email_with_qr
        
        success, message = send_email_with_qr(
            to_email="your-test-email@gmail.com",
            subject="Test Email from ParkEase", 
            html_body="<h1>Test Email</h1><p>If you receive this, email is working!</p>", 
            qr_buffer=None
        )
        
        return f"<h2>Email Test Result</h2><p><strong>Success:</strong> {success}</p><p><strong>Message:</strong> {message}</p>"
        
    except Exception as e:
        return f"<h2>Email Test Error</h2><p><strong>Error:</strong> {str(e)}</p><p><strong>Error Type:</strong> {type(e).__name__}</p>"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        raw_password = request.form.get('password', '')
        fullname = request.form.get('fullname', '').strip()
        address = request.form.get('address', '').strip()
        pincode = request.form.get('pincode', '').strip()

        if not all([email, raw_password, fullname, address, pincode]):
            flash("All fields are required.", 'danger')
            return render_template('signup.html')

        if len(raw_password) < 6:
            flash("Password must be at least 6 characters long.", 'danger')
            return render_template('signup.html')

        if '@' not in email or '.' not in email:
            flash("Please enter a valid email address.", 'danger')
            return render_template('signup.html')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Please login instead.", 'danger')
            return redirect(url_for('signup'))

        try:
            password = generate_password_hash(raw_password)
            new_user = User(
                email=email,
                password=password,
                fullname=fullname,
                address=address,
                pincode=pincode,
                role='user'
            )

            db.session.add(new_user)
            db.session.commit()
            flash("Signup successful. You can now log in.", 'success')
            return redirect(url_for('login'))

        except SQLAlchemyError as e:
            db.session.rollback()
            flash("An error occurred during signup. Please try again.", 'danger')
            print(f"Signup error: {e}")

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Email and password are required", "danger")
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session.permanent = True
            session['user_id'] = user.id
            session['role'] = user.role
            session['user_name'] = user.fullname

            if user.role == 'admin':
                flash(f"Welcome back, {user.fullname}!", 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash(f"Welcome back, {user.fullname}!", 'success')
                return redirect(url_for('user_dashboard'))
        else:
            flash("Invalid email or password", "danger")

    return render_template('login.html')

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    try:
        lots = ParkingLot.query.all()
        for lot in lots:
            lot.spot_statuses = [{'status': spot.status} for spot in lot.spots]

        total_users = User.query.filter_by(role='user').count()
        total_lots = len(lots)
        total_spots = sum(lot.total_spots for lot in lots)
        occupied_spots = sum(lot.occupied_spots_count for lot in lots)
        
        active_users = db.session.query(User.id).join(Reservation).filter(
            and_(User.role == 'user', Reservation.leaving_time == None)
        ).distinct().count()
        
        completed_reservations = db.session.query(
            Reservation.parking_time,
            Reservation.leaving_time,
            Reservation.planned_start_time,
            ParkingLot.price_per_hour
        ).join(ParkingSpot, Reservation.spot_id == ParkingSpot.id)\
        .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id)\
        .filter(Reservation.leaving_time.isnot(None))\
        .all()

        total_revenue = 0
        for parking_time, leaving_time, planned_start_time, price_per_hour in completed_reservations:
            planned_start = planned_start_time or parking_time
            
            if leaving_time < planned_start:
                cost = price_per_hour * 0.25
            else:
                duration = (leaving_time - planned_start).total_seconds() / 3600
                cost = math.ceil(max(0, duration)) * price_per_hour
            
            total_revenue += cost


        stats = {
            'total_users': total_users,
            'total_lots': total_lots,
            'total_spots': total_spots,
            'occupied_spots': occupied_spots,
            'active_users': active_users,
            'total_revenue': round(total_revenue, 2),
            'occupancy_rate': round((occupied_spots/total_spots)*100, 1) if total_spots > 0 else 0
        }

        return render_template('admin_dashboard.html', 
                             parking_lots=lots, 
                             stats=stats,
                             total_spots=total_spots,
                             active_users=active_users,
                             total_revenue=round(total_revenue, 2))

    except SQLAlchemyError as e:
        flash("Error loading dashboard", "danger")
        print(f"Dashboard error: {e}")
        return render_template('admin_dashboard.html', 
                             parking_lots=[], 
                             stats={},
                             total_spots=0,
                             active_users=0,
                             total_revenue=0)


@app.route('/search_parking', methods=['GET'])
@user_required
def search_parking():
    query = request.args.get('location', '').strip()
    results = []

    if query:
        try:
            results = ParkingLot.query.filter(
                (ParkingLot.address.ilike(f'%{query}%')) |
                (ParkingLot.pin_code.ilike(f'%{query}%')) |
                (ParkingLot.prime_location_name.ilike(f'%{query}%'))
            ).all()
            results = [lot for lot in results if lot.available_spots_count > 0]
        except SQLAlchemyError as e:
            flash("Error searching parking lots", "danger")
            print(f"Search error: {e}")

    try:
        reservations = Reservation.query.filter_by(
            user_id=session.get('user_id')
        ).order_by(Reservation.parking_time.desc()).all()
    except SQLAlchemyError as e:
        reservations = []
        print(f"Reservations error: {e}")

    return render_template(
        'user_dashboard.html',
        results=results,
        user_id=session.get('user_id'),
        reservations=reservations,
        search_results=bool(results)
    )

@app.route('/dashboard')
@user_required
def user_dashboard():
    location_query = request.args.get('location', '').strip()
    user_id = session.get('user_id')
    results = []

    if location_query:
        try:
            results = ParkingLot.query.filter(
                (ParkingLot.address.ilike(f"%{location_query}%")) |
                (ParkingLot.pin_code.ilike(f"%{location_query}%")) |
                (ParkingLot.prime_location_name.ilike(f"%{location_query}%"))
            ).all()
            results = [lot for lot in results if lot.available_spots_count > 0]
        except SQLAlchemyError as e:
            flash("Error searching parking lots", "danger")
            print(f"Search error: {e}")

    try:
        reservations = Reservation.query.filter_by(
            user_id=user_id
        ).order_by(Reservation.parking_time.desc()).all()
        
        active_bookings = len([r for r in reservations if r.leaving_time is None])
        
    except SQLAlchemyError as e:
        reservations = []
        active_bookings = 0
        print(f"Reservations error: {e}")

    return render_template('user_dashboard.html',
                         results=results,
                         reservations=reservations,
                         user_id=user_id,
                         active_bookings=active_bookings,
                         search_results=bool(results) if location_query else None)


@app.route('/book/<int:lot_id>/<int:user_id>', methods=['GET', 'POST'])
@user_required
def book_spot(lot_id, user_id):
    if user_id != session.get('user_id'):
        flash('Unauthorized booking attempt', 'danger')
        return redirect(url_for('user_dashboard'))

    if request.method == 'POST':
        vehicle_number = request.form.get('vehicle_number', '').strip()
        booking_date = request.form.get('booking_date', '').strip()
        booking_time = request.form.get('booking_time', '').strip()

        if not all([vehicle_number, booking_date, booking_time]):
            flash('Vehicle number, booking date, and booking time are required', 'danger')
            return redirect(url_for('book_spot', lot_id=lot_id, user_id=user_id))

        try:
            booking_datetime_str = f"{booking_date} {booking_time}"
            booking_datetime = datetime.strptime(booking_datetime_str, '%d-%m-%Y %H:%M')
            
            current_time = datetime.now()
            if booking_datetime < current_time - timedelta(minutes=5):
                flash('Booking time cannot be in the past. Please select a future date and time.', 'danger')
                return redirect(url_for('book_spot', lot_id=lot_id, user_id=user_id))
            
            if booking_datetime > current_time + timedelta(days=30):
                flash('Booking cannot be made more than 30 days in advance.', 'danger')
                return redirect(url_for('book_spot', lot_id=lot_id, user_id=user_id))
            
        except ValueError:
            flash('Invalid date or time format. Please use DD-MM-YYYY for date and HH:MM for time.', 'danger')
            return redirect(url_for('book_spot', lot_id=lot_id, user_id=user_id))

        existing_reservation = Reservation.query.filter_by(
            user_id=user_id,
            leaving_time=None
        ).first()

        if existing_reservation:
            flash('You already have an active parking reservation. Please release it first.', 'danger')
            return redirect(url_for('user_dashboard'))

        try:
            user = User.query.get_or_404(user_id)
            lot = ParkingLot.query.get_or_404(lot_id)

            spot = ParkingSpot.query.filter_by(
                lot_id=lot_id, status='A'
            ).first()

            if not spot:
                flash('No available spots in this lot.', 'danger')
                return redirect(url_for('user_dashboard'))

            spot.status = 'O'

            reservation = Reservation(
                spot_id=spot.id,
                user_id=user_id,
                vehicle_number=vehicle_number,
                parking_time=booking_datetime,
                planned_start_time=booking_datetime
            )

            db.session.add(reservation)
            db.session.commit()

            try:
                qr_buffer = generate_qr_image(f"reservation_id:{reservation.id}")
                html_body = build_booking_email(user, lot, str(reservation.id), booking_datetime)
                success, message = send_email_with_qr(user.email, "Booking Confirmation - ParkEase", html_body, qr_buffer)

                if success:
                    flash("Booking confirmed! Check your email for details.", "success")
                else:
                    flash(f"Booking confirmed! Email notification failed: {message} - Reservation ID: {reservation.id}", "warning")

            except Exception as email_error:
                print(f"Email error: {email_error}")
                flash("Booking confirmed. Email notification failed - please save your reservation ID: {}".format(reservation.id), "warning")

            return redirect(url_for('user_dashboard'))

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Booking error: {e}")
            flash('Booking failed. Please try again.', 'danger')
            return redirect(url_for('user_dashboard'))

    try:
        lot = ParkingLot.query.get_or_404(lot_id)
        available_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()

        if not available_spot:
            flash('No available spots in this lot.', 'danger')
            return redirect(url_for('user_dashboard'))

        return render_template(
            'booking.html',
            user_id=user_id,
            lot_id=lot_id,
            lot=lot,
            spot_id=available_spot.id
        )

    except SQLAlchemyError as e:
        flash('Error loading booking page', 'danger')
        return redirect(url_for('user_dashboard'))

@app.route('/release/<int:reservation_id>', methods=['GET', 'POST'])
@login_required
def release_spot(reservation_id):
    try:
        reservation = Reservation.query.get_or_404(reservation_id)
        spot = ParkingSpot.query.get(reservation.spot_id)
        lot = ParkingLot.query.get(spot.lot_id)

        if session.get('role') == 'user' and reservation.user_id != session.get('user_id'):
            flash('Unauthorized access to reservation', 'danger')
            return redirect(url_for('user_dashboard'))

        if request.method == 'POST':
            try:
                if not reservation.leaving_time:
                    reservation.leaving_time = datetime.utcnow()
                    spot.status = 'A'
                    db.session.commit()

                flash("Spot released successfully!", "success")

                if session.get('role') == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('user_dashboard'))

            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Release error: {e}")
                flash("Could not release spot. Try again.", "danger")

        release_time = datetime.utcnow()
        planned_start = reservation.planned_start_time or reservation.parking_time
        
        if release_time < planned_start:
            total_cost = round(lot.price_per_hour * 0.25, 2)
            time_difference = 0
        else:
            time_difference = (release_time - planned_start).total_seconds() / 3600
            
            if session.get('role') == 'admin':
                total_cost = round(math.ceil(time_difference) * lot.price_per_hour, 2)
            else:
                total_cost = round(math.ceil(time_difference) * lot.price_per_hour, 2)

        template_name = 'release.html' if session.get('role') == 'user' else 'admin_release.html'

        return render_template(
            template_name,
            reservation=reservation,
            spot=spot,
            lot=lot,
            release_time=release_time,
            total_cost=total_cost,
            planned_start=planned_start,
            time_difference=round(max(0, time_difference), 2)
        )

    except SQLAlchemyError as e:
        flash('Error accessing reservation', 'danger')
        return redirect(url_for('user_dashboard') if session.get('role') == 'user' else url_for('admin_dashboard'))


@app.route('/add_lot', methods=['GET', 'POST'])
@admin_required
def add_lot():
    if request.method == 'POST':
        prime_location_name = request.form.get('prime_location_name', '').strip()
        address = request.form.get('address', '').strip()
        pin_code = request.form.get('pin_code', '').strip()
        price_per_hour = request.form.get('price_per_hour')
        available_spots = request.form.get('available_spots')

        if not all([prime_location_name, address, pin_code, price_per_hour, available_spots]):
            flash("All fields are required.", 'danger')
            return render_template('add_lot.html')

        try:
            price_per_hour = float(price_per_hour)
            available_spots = int(available_spots)

            if price_per_hour <= 0 or available_spots <= 0:
                flash("Price and spots must be positive numbers.", 'danger')
                return render_template('add_lot.html')

        except ValueError:
            flash("Invalid price or spots number.", 'danger')
            return render_template('add_lot.html')

        try:
            new_lot = ParkingLot(
                prime_location_name=prime_location_name,
                address=address,
                pin_code=pin_code,
                price_per_hour=price_per_hour
            )

            db.session.add(new_lot)
            db.session.flush()

            for _ in range(available_spots):
                spot = ParkingSpot(lot_id=new_lot.id, status='A')
                db.session.add(spot)

            db.session.commit()
            flash(f"Parking lot '{prime_location_name}' added successfully!", 'success')
            return redirect(url_for('admin_dashboard'))

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Add lot error: {e}")
            flash("Error creating parking lot. Please try again.", 'danger')

    return render_template('add_lot.html')

@app.route('/view_users')
@admin_required
def view_users():
    try:
        users = User.query.filter(User.role != 'admin').all()
        return render_template('view_users.html', users=users)
    except SQLAlchemyError as e:
        flash("Error loading users", "danger")
        print(f"View users error: {e}")
        return redirect(url_for('admin_dashboard'))


@app.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
def edit_lot(lot_id):
    try:
        lot = ParkingLot.query.get_or_404(lot_id)
        error_message = None

        if request.method == 'POST':
            prime_location_name = request.form.get('prime_location_name', '').strip()
            address = request.form.get('address', '').strip()
            pin_code = request.form.get('pin_code', '').strip()
            price_per_hour = request.form.get('price_per_hour')
            new_total_spots = request.form.get('available_spots')

            if not all([prime_location_name, address, pin_code, price_per_hour, new_total_spots]):
                error_message = "All fields are required."
                return render_template('edit_lot.html', lot=lot, error_message=error_message)

            try:
                price_per_hour = float(price_per_hour)
                new_total_spots = int(new_total_spots)

                if price_per_hour <= 0 or new_total_spots <= 0:
                    error_message = "Price and spots must be positive numbers."
                    return render_template('edit_lot.html', lot=lot, error_message=error_message)

            except ValueError:
                error_message = "Invalid price or spots number."
                return render_template('edit_lot.html', lot=lot, error_message=error_message)

            try:
                lot.prime_location_name = prime_location_name
                lot.address = address
                lot.pin_code = pin_code
                lot.price_per_hour = price_per_hour

                current_total_spots = lot.total_spots

                if new_total_spots > current_total_spots:
                    for _ in range(new_total_spots - current_total_spots):
                        new_spot = ParkingSpot(lot_id=lot.id, status='A')
                        db.session.add(new_spot)

                elif new_total_spots < current_total_spots:
                    spots_to_remove = current_total_spots - new_total_spots

                    available_spots = []
                    for spot in lot.spots:
                        if spot.status == 'A':
                            has_reservations = Reservation.query.filter_by(spot_id=spot.id).first()
                            if not has_reservations:
                                available_spots.append(spot)

                    if spots_to_remove > len(available_spots):
                        error_message = "Cannot reduce spots: Not enough unused available spots to remove."
                        return render_template('edit_lot.html', lot=lot, error_message=error_message)

                    spots_to_delete = available_spots[:spots_to_remove]
                    for spot in spots_to_delete:
                        db.session.delete(spot)

                db.session.commit()
                flash(f"Lot '{lot.prime_location_name}' updated successfully!", 'success')
                return redirect(url_for('admin_dashboard'))

            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Edit lot error: {e}")
                error_message = "Error updating lot. Please try again."

        return render_template('edit_lot.html', lot=lot, error_message=error_message)

    except SQLAlchemyError as e:
        flash("Error accessing lot", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/delete_lot_confirm/<int:lot_id>')
@admin_required
def delete_lot_confirm(lot_id):
    try:
        lot = ParkingLot.query.get_or_404(lot_id)
        return render_template('delete_lot.html', lot=lot)
    except SQLAlchemyError as e:
        flash("Error accessing lot", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/delete_lot/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
def delete_lot(lot_id):
    try:
        lot = ParkingLot.query.get_or_404(lot_id)
        error_message = None

        if request.method == 'POST':
            occupied_spots = [s for s in lot.spots if s.status == 'O']
            if occupied_spots:
                occupied_count = len(occupied_spots)
                error_message = f"Cannot delete lot: {occupied_count} spot(s) are currently occupied. Please wait for all users to release their spots first."
                return render_template('delete_lot.html', lot=lot, error_message=error_message)

            try:
                for spot in lot.spots:
                    reservations = Reservation.query.filter_by(spot_id=spot.id).all()
                    for res in reservations:
                        db.session.delete(res)
                    db.session.delete(spot)

                db.session.delete(lot)
                db.session.commit()

                flash(f"Lot '{lot.prime_location_name}' deleted successfully!", 'success')
                return redirect(url_for('admin_dashboard'))

            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Delete lot error: {e}")
                error_message = "Error deleting lot. Please try again."

        return render_template('delete_lot.html', lot=lot, error_message=error_message)

    except SQLAlchemyError as e:
        flash("Error accessing lot", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/delete_spot/<int:spot_id>', methods=['GET'])
@admin_required
def delete_spot(spot_id):
    try:
        spot = ParkingSpot.query.get_or_404(spot_id)
        return render_template('delete_spot.html', spot=spot)
    except SQLAlchemyError as e:
        flash("Error accessing spot", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/delete_spot_final/<int:spot_id>', methods=['POST'])
@admin_required
def delete_spot_final(spot_id):
    try:
        spot = ParkingSpot.query.get_or_404(spot_id)

        if spot.status == 'O':
            flash("Cannot delete occupied spot. Please wait for the user to release it first.", "danger")
            return redirect(url_for('spot_details', spot_id=spot_id))

        try:
            reservations = Reservation.query.filter_by(spot_id=spot.id).all()
            for res in reservations:
                db.session.delete(res)

            db.session.delete(spot)
            db.session.commit()

            flash("Spot deleted successfully!", 'success')
            return redirect(url_for('admin_dashboard'))

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Delete spot error: {e}")
            flash("Error deleting spot. Please try again.", 'danger')
            return redirect(url_for('delete_spot', spot_id=spot_id))

    except SQLAlchemyError as e:
        flash("Error accessing spot", "danger")
        return redirect(url_for('admin_dashboard'))


@app.route('/spot_details/<int:spot_id>', methods=['GET'])
@admin_required
def spot_details(spot_id):
    try:
        spot = ParkingSpot.query.get_or_404(spot_id)
        
        if spot.status == 'A':
            return redirect(url_for('delete_spot', spot_id=spot_id))
        
        reservation = Reservation.query.filter_by(
            spot_id=spot_id,
            leaving_time=None
        ).first()

        if not reservation:
            flash("No active reservation found for this spot", "warning")
            return redirect(url_for('admin_dashboard'))

        user = User.query.get(reservation.user_id)
        
        now = datetime.utcnow()
        planned_start = reservation.planned_start_time or reservation.parking_time
        
        if now < planned_start:
            hours_parked = 0
            estimated_cost = spot.lot.price_per_hour * 0.25 
            status_message = "Scheduled - Not Started"
        else:
            hours_parked = (now - planned_start).total_seconds() / 3600
            estimated_cost = math.ceil(hours_parked) * spot.lot.price_per_hour
            status_message = "Active Parking"

        return render_template('spot_details.html',
                             spot=spot,
                             reservation=reservation,
                             user=user,
                             hours_parked=round(max(0, hours_parked), 2),
                             estimated_cost=round(estimated_cost, 2),
                             planned_start=planned_start,
                             status_message=status_message)

    except SQLAlchemyError as e:
        flash("Error accessing spot details", "danger")
        print(f"Spot details error: {e}")
        return redirect(url_for('admin_dashboard'))


@app.route('/admin_search', methods=['GET'])
@admin_required
def admin_search():
    query = request.args.get('search_query', '').strip()
    search_by = request.args.get('search_by', '')
    spots = []
    user = None

    if query:
        try:
            if search_by == 'user_id' or query.isdigit():
                user_id = int(query)
                user = User.query.filter_by(id=user_id, role='user').first()
                
                if user:
                    active_reservations = Reservation.query.filter_by(
                        user_id=user_id,
                        leaving_time=None
                    ).all()
                    
                    spots = []
                    for reservation in active_reservations:
                        spot = ParkingSpot.query.get(reservation.spot_id)
                        if spot:
                            spot.reservation = reservation
                            spot.user = user
                            spots.append(spot)

            elif search_by == 'username':
                user = User.query.filter(
                    User.fullname.ilike(f'%{query}%'),
                    User.role == 'user'
                ).first()
                
                if user:
                    active_reservations = Reservation.query.filter_by(
                        user_id=user.id,
                        leaving_time=None
                    ).all()
                    
                    spots = []
                    for reservation in active_reservations:
                        spot = ParkingSpot.query.get(reservation.spot_id)
                        if spot:
                            spot.reservation = reservation
                            spot.user = user
                            spots.append(spot)

            else:
                if query.isdigit():
                    user = User.query.filter_by(id=int(query), role='user').first()
                else:
                    user = User.query.filter(
                        User.fullname.ilike(f'%{query}%'),
                        User.role == 'user'
                    ).first()
                
                if user:
                    active_reservations = Reservation.query.filter_by(
                        user_id=user.id,
                        leaving_time=None
                    ).all()
                    
                    spots = []
                    for reservation in active_reservations:
                        spot = ParkingSpot.query.get(reservation.spot_id)
                        if spot:
                            spot.reservation = reservation
                            spot.user = user
                            spots.append(spot)

        except (ValueError, SQLAlchemyError) as e:
            flash("Error performing search", "danger")
            print(f"Search error: {e}")

    return render_template('admin_search.html',
                         spots=spots,
                         user=user,
                         query=query,
                         search_by=search_by)

@app.route('/scan_release/<int:spot_id>')
@admin_required
def scan_release(spot_id):
    try:
        spot = ParkingSpot.query.get_or_404(spot_id)
        
        if spot.status != 'O':
            flash("This spot is not occupied", "warning")
            return redirect(url_for('admin_dashboard'))
        
        reservation = Reservation.query.filter_by(
            spot_id=spot_id,
            leaving_time=None
        ).first()
        
        if not reservation:
            flash("No active reservation found", "warning")
            return redirect(url_for('admin_dashboard'))
        
        return render_template('scan_release.html', 
                             spot=spot, 
                             reservation=reservation)
    
    except SQLAlchemyError as e:
        flash("Error accessing scan page", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/verify_qr', methods=['POST'])
@admin_required
def verify_qr():
    try:
        data = request.get_json()
        qr_data = data.get('qr_data', '')
        spot_id = data.get('spot_id')
        
        if qr_data.startswith('reservation_id:'):
            reservation_id = int(qr_data.split(':')[1])
            
            reservation = Reservation.query.filter_by(
                id=reservation_id,
                spot_id=spot_id,
                leaving_time=None
            ).first()
            
            if reservation:
                return jsonify({
                    'success': True,
                    'reservation_id': reservation_id,
                    'redirect_url': url_for('admin_release_spot', reservation_id=reservation_id)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid QR code or reservation not found'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid QR code format'
            })
    
    except (ValueError, SQLAlchemyError) as e:
        return jsonify({
            'success': False,
            'error': 'Error processing QR code'
        })

@app.route('/admin_release/<int:reservation_id>', methods=['GET', 'POST'])
@admin_required
def admin_release_spot(reservation_id):
    try:
        reservation = Reservation.query.get_or_404(reservation_id)
        spot = ParkingSpot.query.get(reservation.spot_id)
        lot = ParkingLot.query.get(spot.lot_id)

        if request.method == 'POST':
            try:
                if not reservation.leaving_time:
                    reservation.leaving_time = datetime.utcnow()
                    spot.status = 'A'
                    db.session.commit()

                flash("Spot released successfully via admin scan!", "success")
                return redirect(url_for('admin_dashboard'))

            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Admin release error: {e}")
                flash("Could not release spot. Try again.", "danger")

        release_time = datetime.utcnow()
        planned_start = reservation.planned_start_time or reservation.parking_time
        
        if release_time < planned_start:
            total_cost = round(lot.price_per_hour * 0.25, 2)
            time_difference = 0
        else:
            time_difference = (release_time - planned_start).total_seconds() / 3600
            total_cost = round(math.ceil(time_difference) * lot.price_per_hour, 2)

        return render_template(
            'admin_release.html',
            reservation=reservation,
            spot=spot,
            lot=lot,
            release_time=release_time,
            total_cost=total_cost,
            planned_start=planned_start,
            time_difference=round(max(0, time_difference), 2)
        )

    except SQLAlchemyError as e:
        flash('Error accessing reservation', 'danger')
        return redirect(url_for('admin_dashboard'))


@app.route('/edit_profile_user', methods=['GET', 'POST'])
@user_required
def edit_profile_user():
    try:
        user = User.query.get_or_404(session['user_id'])
        error_message = None

        if request.method == 'POST':
            fullname = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not fullname or not email:
                error_message = "Name and email are required."
                return render_template('edit_profile_user.html', user=user, error_message=error_message)

            existing_user = User.query.filter(User.email == email, User.id != user.id).first()
            if existing_user:
                error_message = "Email already in use by another account."
                return render_template('edit_profile_user.html', user=user, error_message=error_message)

            if new_password:
                if new_password != confirm_password:
                    error_message = "Passwords do not match."
                    return render_template('edit_profile_user.html', user=user, error_message=error_message)

                if len(new_password) < 6:
                    error_message = "Password must be at least 6 characters long."
                    return render_template('edit_profile_user.html', user=user, error_message=error_message)

            try:
                user.fullname = fullname
                user.email = email

                if new_password:
                    user.password = generate_password_hash(new_password)

                db.session.commit()
                flash("Profile updated successfully!", 'success')
                return redirect(url_for('user_dashboard'))

            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Profile update error: {e}")
                error_message = "Error updating profile. Please try again."

        return render_template('edit_profile_user.html', user=user, error_message=error_message)

    except SQLAlchemyError as e:
        flash("Error accessing profile", "danger")
        return redirect(url_for('user_dashboard'))

@app.route('/edit_profile_admin', methods=['GET', 'POST'])
@admin_required
def edit_profile_admin():
    try:
        admin = User.query.get_or_404(session['user_id'])
        error_message = None

        if request.method == 'POST':
            fullname = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not fullname or not email:
                error_message = "Name and email are required."
                return render_template('edit_profile_admin.html', admin=admin, error_message=error_message)

            existing_user = User.query.filter(User.email == email, User.id != admin.id).first()
            if existing_user:
                error_message = "Email already in use by another account."
                return render_template('edit_profile_admin.html', admin=admin, error_message=error_message)

            if new_password:
                if new_password != confirm_password:
                    error_message = "Passwords do not match."
                    return render_template('edit_profile_admin.html', admin=admin, error_message=error_message)

                if len(new_password) < 6:
                    error_message = "Password must be at least 6 characters long."
                    return render_template('edit_profile_admin.html', admin=admin, error_message=error_message)

            try:
                admin.fullname = fullname
                admin.email = email

                if new_password:
                    admin.password = generate_password_hash(new_password)

                db.session.commit()
                flash("Profile updated successfully!", 'success')
                return redirect(url_for('admin_dashboard'))

            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Profile update error: {e}")
                error_message = "Error updating profile. Please try again."

        return render_template('edit_profile_admin.html', admin=admin, error_message=error_message)

    except SQLAlchemyError as e:
        flash("Error accessing profile", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/user_summary')
@user_required
def user_summary():
    try:
        user_id = session.get('user_id')
        
        reservations = (
            db.session.query(Reservation, ParkingLot)
            .join(ParkingSpot, Reservation.spot_id == ParkingSpot.id)
            .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id)
            .filter(Reservation.user_id == user_id)
            .filter(Reservation.leaving_time.isnot(None))
            .all()
        )

        lot_times = {}
        for res, lot in reservations:
            planned_start = res.planned_start_time or res.parking_time
            
            if res.leaving_time > planned_start:
                time_spent = (res.leaving_time - planned_start).total_seconds() / 3600
                time_spent = max(0, time_spent)
                
                if time_spent > 0.01:
                    if lot.prime_location_name in lot_times:
                        lot_times[lot.prime_location_name] += time_spent
                    else:
                        lot_times[lot.prime_location_name] = time_spent

        labels = list(lot_times.keys())
        data = [round(t, 2) for t in lot_times.values()]

        return render_template('user_summary.html', labels=labels, data=data)

    except SQLAlchemyError as e:
        flash("Error loading summary", "danger")
        print(f"User summary error: {e}")
        return render_template('user_summary.html', labels=[], data=[])

@app.route('/admin_summary')
@admin_required
def admin_summary():
    try:
        completed_reservations = db.session.query(
            ParkingLot.prime_location_name,
            ParkingLot.price_per_hour,
            Reservation.parking_time,
            Reservation.leaving_time,
            Reservation.planned_start_time
        ).join(ParkingSpot, ParkingLot.id == ParkingSpot.lot_id)\
         .join(Reservation, Reservation.spot_id == ParkingSpot.id)\
         .filter(Reservation.leaving_time.isnot(None))\
         .all()

        lot_revenue = defaultdict(float)
        for lot_name, price_per_hour, parking_time, leaving_time, planned_start_time in completed_reservations:
            planned_start = planned_start_time or parking_time
            
            if leaving_time < planned_start:
                cost = price_per_hour * 0.25
            else:
                duration = (leaving_time - planned_start).total_seconds() / 3600
                cost = math.ceil(max(0.01, duration)) * price_per_hour
            
            lot_revenue[lot_name] += cost


        lot_names = list(lot_revenue.keys()) if lot_revenue else []
        revenue_values = [round(lot_revenue[name], 2) for name in lot_names] if lot_names else []

        lot_spot_counts = db.session.query(
            ParkingLot.prime_location_name,
            ParkingSpot.status,
            db.func.count(ParkingSpot.id)
        ).join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id)\
        .group_by(ParkingLot.prime_location_name, ParkingSpot.status)\
        .all()

        status_labels = list(set(lot_name for lot_name, _, _ in lot_spot_counts)) if lot_spot_counts else []
        available_counts, occupied_counts = [], []

        for lot_name in status_labels:
            available = sum(count for ln, status, count in lot_spot_counts if ln == lot_name and status == 'A')
            occupied = sum(count for ln, status, count in lot_spot_counts if ln == lot_name and status == 'O')
            available_counts.append(available)
            occupied_counts.append(occupied)

        return render_template(
            'admin_summary.html',
            lot_names=lot_names,
            revenue_values=revenue_values,
            status_labels=status_labels,
            available_counts=available_counts,
            occupied_counts=occupied_counts
        )

    except SQLAlchemyError as e:
        flash("Error loading summary", "danger")
        print(f"Admin summary error: {e}")
        return render_template(
            'admin_summary.html',
            lot_names=[],
            revenue_values=[],
            status_labels=[],
            available_counts=[],
            occupied_counts=[]
        )

@app.route('/check_availability/<int:lot_id>')
@user_required
def check_availability(lot_id):
    """AJAX endpoint to check real-time availability"""
    try:
        lot = ParkingLot.query.get_or_404(lot_id)
        return jsonify({
            'available_spots': lot.available_spots_count,
            'total_spots': lot.total_spots,
            'occupancy_rate': round((lot.occupied_spots_count / lot.total_spots) * 100, 1) if lot.total_spots > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': 'Could not fetch availability'}), 500

@app.route('/user_active_reservation')
@user_required
def user_active_reservation():
    """Get user's active reservation if any"""
    try:
        user_id = session.get('user_id')
        active_reservation = db.session.query(Reservation, ParkingSpot, ParkingLot)\
            .join(ParkingSpot, Reservation.spot_id == ParkingSpot.id)\
            .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id)\
            .filter(and_(Reservation.user_id == user_id, Reservation.leaving_time == None))\
            .first()

        if active_reservation:
            res, spot, lot = active_reservation
            current_time = datetime.utcnow()
            duration = (current_time - res.parking_time).total_seconds() / 3600
            cost = round(math.ceil(duration) * lot.price_per_hour, 2)

            return render_template('active_reservation.html',
                                 reservation=res,
                                 lot=lot,
                                 duration=round(duration, 2),
                                 estimated_cost=cost)
        else:
            flash("No active reservation found", "info")
            return redirect(url_for('user_dashboard'))

    except SQLAlchemyError as e:
        flash("Error fetching active reservation", "danger")
        print(f"Active reservation error: {e}")
        return redirect(url_for('user_dashboard'))

@app.route('/reservation_history/<int:user_id>')
@login_required
def reservation_history(user_id):
    """View reservation history for a user"""
    try:
        if session.get('role') == 'user' and user_id != session.get('user_id'):
            flash('Unauthorized access', 'danger')
            return redirect(url_for('user_dashboard'))

        user = User.query.get_or_404(user_id)
        reservations = db.session.query(Reservation, ParkingSpot, ParkingLot)\
            .join(ParkingSpot, Reservation.spot_id == ParkingSpot.id)\
            .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id)\
            .filter(Reservation.user_id == user_id)\
            .order_by(Reservation.parking_time.desc())\
            .all()

        reservation_data = []
        total_spent = 0

        for res, spot, lot in reservations:
            cost = 0
            if res.leaving_time:
                duration = (res.leaving_time - res.parking_time).total_seconds() / 3600
                cost = round(math.ceil(duration) * lot.price_per_hour, 2)
                total_spent += cost

            reservation_data.append({
                'reservation': res,
                'spot': spot,
                'lot': lot,
                'cost': cost
            })

        return render_template('reservation_history.html',
                             user=user,
                             reservation_data=reservation_data,
                             total_spent=round(total_spent, 2))

    except SQLAlchemyError as e:
        flash("Error loading reservation history", "danger")
        print(f"Reservation history error: {e}")
        return redirect(url_for('user_dashboard') if session.get('role') == 'user' else url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", 'info')
    return redirect(url_for('login'))

@app.errorhandler(404)
def not_found_error(error):
    flash("Page not found", 'danger')
    return redirect(url_for('home'))

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    flash("An internal error occurred", 'danger')
    return redirect(url_for('home'))

@app.errorhandler(403)
def forbidden_error(error):
    flash("Access forbidden", 'danger')
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully!")

            if not User.query.filter_by(role='admin').first():
                hashed_pw = generate_password_hash("admin123")
                admin = User(
                    email="admin@parkease.com",
                    password=hashed_pw,
                    fullname="Administrator",
                    address="Admin Office",
                    pincode="000000",
                    role="admin"
                )

                db.session.add(admin)
                db.session.commit()
                print("✅ Default admin created!")
                print("📧 Email: admin@parkease.com")
                print("🔑 Password: admin123")

        except SQLAlchemyError as e:
            print(f"❌ Database initialization error: {e}")
            
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
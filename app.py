from flask import Flask, render_template, request, redirect, url_for, flash, session
from models.models import db, User, ParkingLot, ParkingSpot, Reservation, RecentBooking
from datetime import datetime
from flask_login import current_user

app = Flask(__name__)
app.secret_key = 'secret-key'

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Home redirects to login
@app.route('/')
def home():
    return redirect(url_for('login'))

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        fullname = request.form['fullname']
        address = request.form['address']
        pincode = request.form['pincode']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Please login instead.", 'danger')
            return redirect(url_for('signup'))

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

    return render_template('signup.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role

            flash("Login successful", "success")
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash("Invalid credentials", "danger")

    return render_template('login.html')


@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    lots = ParkingLot.query.all()
    return render_template('admin_dashboard.html', lots=lots)


@app.route('/search_parking', methods=['GET'])
def search_parking():
    query = request.args.get('location')
    results = []

    if query:
        results = ParkingLot.query.filter(
            (ParkingLot.address.ilike(f'%{query}%')) |
            (ParkingLot.pin_code.ilike(f'%{query}%'))
        ).all()

        # Now filter dynamically using the property
        results = [lot for lot in results if lot.available_spots_count > 0]

    reservations = Reservation.query.filter_by(user_id=session.get('user_id')).order_by(Reservation.parking_time.desc()).all()

    return render_template(
        'user_dashboard.html',
        results=results,
        user_id=session.get('user_id'),
        reservations=reservations,
        search_results=bool(results)
    )

# User Dashboard route
@app.route('/dashboard')
def user_dashboard():
    location_query = request.args.get('location', '')
    user_id = session.get('user_id')

    if location_query:
        results = ParkingLot.query.filter(
            (ParkingLot.address.ilike(f"%{location_query}%")) |
            (ParkingLot.pin_code.ilike(f"%{location_query}%"))
        ).filter(ParkingLot.available_spots > 0).all()
    else:
        results = []

    reservations = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.parking_time.desc()).all()

    return render_template('user_dashboard.html', results=results, reservations=reservations, user_id=session.get('user_id'))


@app.route('/book/<int:lot_id>/<int:user_id>', methods=['GET', 'POST'])
def book_spot(lot_id, user_id):
    if request.method == 'POST':
        user_id = request.form['user_id']
        lot_id = request.form['lot_id']
        spot_id = request.form['spot_id']
        vehicle_number = request.form['vehicle_number']

        try:
            with db.session.begin_nested():
                spot = ParkingSpot.query.get(spot_id)
                if not spot or spot.status != 'A':
                    flash('Invalid or already occupied spot.', 'danger')
                    return redirect(url_for('user_dashboard'))

                # Mark spot occupied
                spot.status = 'O'

                # Create new reservation
                reservation = Reservation(
                    spot_id=spot_id,
                    user_id=user_id,
                    vehicle_number=vehicle_number
                )
                db.session.add(reservation)

            db.session.commit()
            flash('Spot reserved successfully!', 'success')

        except Exception as e:
            db.session.rollback()
            print(f"Booking error: {e}")
            flash('Something went wrong. Try again.', 'danger')

        return redirect(url_for('user_dashboard'))

    # GET — fetch first available spot
    available_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    if not available_spot:
        flash('No available spots.', 'danger')
        return redirect(url_for('user_dashboard'))

    return render_template(
        'booking.html',
        user_id=user_id,
        lot_id=lot_id,
        spot_id=available_spot.id
    )


@app.route('/release/<int:reservation_id>', methods=['GET', 'POST'])
def release_spot(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    spot = ParkingSpot.query.get(reservation.spot_id)
    lot = ParkingLot.query.get(spot.lot_id)

    if request.method == 'POST':
        try:
            with db.session.begin_nested():
                # Set leaving time if not already set
                if not reservation.leaving_time:
                    reservation.leaving_time = datetime.utcnow()
                    spot.status = 'A'
                    db.session.flush()  # to reflect changes immediately for property

            db.session.commit()
            flash("Parking spot released successfully!", "success")
            return redirect(url_for("user_dashboard"))

        except Exception as e:
            db.session.rollback()
            print(f"Release error: {e}")
            flash("Could not release spot. Try again.", "danger")

    # Calculate cost
    release_time = datetime.utcnow()
    parking_duration = (release_time - reservation.parking_time).total_seconds() / 3600
    total_cost = round(parking_duration * 150, 2)

    return render_template(
        'release.html',
        reservation=reservation,
        spot=spot,
        lot=lot,
        release_time=release_time,
        total_cost=total_cost
    )


@app.route('/add_lot', methods=['GET', 'POST'])
def add_lot():
    if request.method == 'POST':
        prime_location_name = request.form['prime_location_name']
        address = request.form['address']
        pin_code = request.form['pin_code']
        price_per_hour = request.form['price_per_hour']
        available_spots = request.form['available_spots']

        new_lot = ParkingLot(
            prime_location_name=prime_location_name,
            address=address,
            pin_code=pin_code,
            price_per_hour=price_per_hour,
            available_spots=available_spots
        )
        db.session.add(new_lot)
        db.session.commit()

        flash("Parking lot added successfully.", 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_lot.html')


# Dummy Logout route (fix for your navbar link)
@app.route('/logout')
def logout():
    flash("Logged out successfully!", 'info')
    return redirect(url_for('login'))

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        try:
            with db.session.begin_nested():
                if not User.query.filter_by(role='admin').first():
                    admin = User(email="admin@app.com", password="admin123", role="admin")
                    db.session.add(admin)
                    print("✅ Default admin created!")

                if not ParkingLot.query.first():
                    lot1 = ParkingLot(id=101, prime_location_name="City Center", address="12 MG Road, Kolkata",
                                      pin_code="700001", price_per_hour=50, available_spots=5)
                    lot2 = ParkingLot(id=102, prime_location_name="Salt Lake Sector V", address="DLF IT Park, Kolkata",
                                      pin_code="700091", price_per_hour=40, available_spots=3)
                    lot3 = ParkingLot(id=103, prime_location_name="South City",
                                      address="375 Prince Anwar Shah Road", pin_code="700068",
                                      price_per_hour=60, available_spots=7)

                    db.session.add_all([lot1, lot2, lot3])
                    print("✅ Dummy parking lots seeded!")

                    # Seed spots too
                    db.session.add_all([ParkingSpot(lot_id=101, status='A') for _ in range(5)])
                    db.session.add_all([ParkingSpot(lot_id=102, status='A') for _ in range(3)])
                    db.session.add_all([ParkingSpot(lot_id=103, status='A') for _ in range(7)])
                    print("✅ Dummy parking spots seeded!")

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Seeding error: {e}")

    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, flash, session
from models.models import db, User, ParkingLot, ParkingSpot, Reservation
from datetime import datetime
from flask_login import current_user
from collections import defaultdict
import math

app = Flask(__name__)
app.secret_key = 'secret-key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@app.route('/')
def home():
    return redirect(url_for('login'))

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role

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

    for lot in lots:
        lot.spot_statuses = [{'status': spot.status} for spot in lot.spots]

    return render_template('admin_dashboard.html', parking_lots=lots)



@app.route('/search_parking', methods=['GET'])
def search_parking():
    query = request.args.get('location')
    results = []

    if query:
        results = ParkingLot.query.filter(
            (ParkingLot.address.ilike(f'%{query}%')) |
            (ParkingLot.pin_code.ilike(f'%{query}%'))
        ).all()

        results = [lot for lot in results if lot.available_spots_count > 0]

    reservations = Reservation.query.filter_by(user_id=session.get('user_id')).order_by(Reservation.parking_time.desc()).all()

    return render_template(
        'user_dashboard.html',
        results=results,
        user_id=session.get('user_id'),
        reservations=reservations,
        search_results=bool(results)
    )

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

                spot.status = 'O'

                reservation = Reservation(
                    spot_id=spot_id,
                    user_id=user_id,
                    vehicle_number=vehicle_number
                )
                db.session.add(reservation)

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Booking error: {e}")
            flash('Something went wrong. Try again.', 'danger')

        return redirect(url_for('user_dashboard'))

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
                if not reservation.leaving_time:
                    reservation.leaving_time = datetime.utcnow()
                    spot.status = 'A'
                    db.session.flush()

            db.session.commit()
            return redirect(url_for("user_dashboard"))

        except Exception as e:
            db.session.rollback()
            print(f"Release error: {e}")
            flash("Could not release spot. Try again.", "danger")

    release_time = datetime.utcnow()
    parking_duration = (release_time - reservation.parking_time).total_seconds() / 3600
    total_cost = round(parking_duration * lot.price_per_hour, 2)

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

        for _ in range(int(available_spots)):
            spot = ParkingSpot(lot_id=new_lot.id, status='A')
            db.session.add(spot)

        db.session.commit()


        return redirect(url_for('admin_dashboard'))

    return render_template('add_lot.html')

@app.route('/view_users')
def view_users():
    if session.get('role') != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    users = User.query.filter(User.role != 'admin').all()
    return render_template('view_users.html', users=users)

@app.route('/admin_search', methods=['GET'])
def admin_search():
    if session.get('role') != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    query = request.args.get('search_query')
    search_by = request.args.get('search_by')

    lots = []

    if query:
        if search_by == 'user_id':
            reservations = Reservation.query.filter_by(user_id=query, leaving_time=None).all()
            lot_ids = list(set(r.spot.lot_id for r in reservations))
            lots = ParkingLot.query.filter(ParkingLot.id.in_(lot_ids)).all()

        elif search_by == 'location':
            lots = ParkingLot.query.filter(ParkingLot.prime_location_name.ilike(f'%{query}%')).all()

        else:
            if query.isdigit():
                reservations = Reservation.query.filter_by(user_id=query, leaving_time=None).all()
                lot_ids = list(set(r.spot.lot_id for r in reservations))
                lots += ParkingLot.query.filter(ParkingLot.id.in_(lot_ids)).all()

            lots += ParkingLot.query.filter(ParkingLot.prime_location_name.ilike(f'%{query}%')).all()

        lots = list({lot.id: lot for lot in lots}.values())

    return render_template('admin_search.html', lots=lots, query=query, search_by=search_by)


@app.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    error_message = None

    if request.method == 'POST':
        lot.prime_location_name = request.form['prime_location_name']
        lot.address = request.form['address']
        lot.pin_code = request.form['pin_code']
        lot.price_per_hour = request.form['price_per_hour']

        new_total_spots = int(request.form['available_spots'])
        current_total_spots = lot.total_spots

        if new_total_spots > current_total_spots:
            for _ in range(new_total_spots - current_total_spots):
                new_spot = ParkingSpot(lot_id=lot.id, status='A')
                db.session.add(new_spot)

        elif new_total_spots < current_total_spots:
            spots_to_remove = current_total_spots - new_total_spots

            available_spots = []
            for s in lot.spots:
                if s.status == 'A':
                    has_reservations = Reservation.query.filter_by(spot_id=s.id).count()
                    if has_reservations == 0:
                        available_spots.append(s)

            if spots_to_remove > len(available_spots):
                error_message = "Couldn't proceed with the update as reserved spots can't be deleted."
                return render_template('edit_lot.html', lot=lot, error_message=error_message)

            spots_selected_for_delete = available_spots[:spots_to_remove]
            for spot in spots_selected_for_delete:
                db.session.delete(spot)

        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_lot.html', lot=lot, error_message=error_message)

@app.route('/delete_lot_confirm/<int:lot_id>')
def delete_lot_confirm(lot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    return render_template('delete_lot.html', lot=lot)


@app.route('/delete_lot/<int:lot_id>', methods=['GET', 'POST'])
def delete_lot(lot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    error_message = None

    if request.method == 'POST':
        occupied_or_reserved_spots = [s for s in lot.spots if s.status == 'O']

        if occupied_or_reserved_spots:
            error_message = "Lots with reserved or occupied spots can't be deleted."
            return render_template('delete_lot.html', lot=lot, error_message=error_message)

        for spot in lot.spots:
            db.session.delete(spot)

        db.session.delete(lot)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('delete_lot.html', lot=lot)

@app.route('/delete_spot/<int:spot_id>', methods=['GET'])
def delete_spot(spot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    spot = ParkingSpot.query.get_or_404(spot_id)
    return render_template('delete_spot.html', spot=spot)

@app.route('/delete_spot_final/<int:spot_id>', methods=['POST'])
def delete_spot_final(spot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    spot = ParkingSpot.query.get_or_404(spot_id)

    if spot.status == 'O':
        error_message = "Occupied spots can't be deleted."
        return render_template('delete_spot.html', spot=spot, error_message=error_message)

    lot_id = spot.lot_id
    db.session.delete(spot)
    db.session.commit()

    return redirect(url_for('admin_dashboard'))

@app.route('/spot_details/<int:spot_id>', methods=['GET'])
def spot_details(spot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    spot = ParkingSpot.query.get_or_404(spot_id)

    reservation = Reservation.query.filter_by(spot_id=spot_id, leaving_time=None).first()

    if not reservation:
        return redirect(url_for('delete_spot', spot_id=spot_id))

    from datetime import datetime
    now = datetime.now()
    hours_parked = (now - reservation.parking_time).total_seconds() / 3600
    cost_per_hour = spot.lot.price_per_hour
    est_cost = round(hours_parked * cost_per_hour, 2)

    return render_template('spot_details.html', spot=spot, reservation=reservation, est_cost=est_cost)

@app.route('/edit_profile_user', methods=['GET', 'POST'])
def edit_profile_user():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(session['user_id'])
    error_message = None

    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']

        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password and new_password != confirm_password:
            error_message = "Passwords do not match."
            return render_template('edit_profile_user.html', user=user, error_message=error_message)

        if new_password:
            user.password = new_password

        db.session.commit()
        return redirect(url_for('user_dashboard'))

    return render_template('edit_profile_user.html', user=user)

@app.route('/edit_profile_admin', methods=['GET', 'POST'])
def edit_profile_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    admin = User.query.get_or_404(session['user_id'])
    error_message = None

    if request.method == 'POST':
        admin.name = request.form['name']
        admin.email = request.form['email']

        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password and new_password != confirm_password:
            error_message = "Passwords do not match."
            return render_template('edit_profile_admin.html', admin=admin, error_message=error_message)

        if new_password:
            admin.password = new_password

        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_profile_admin.html', admin=admin)

@app.route('/user_summary')
def user_summary():
    if session.get('role') != 'user':
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    reservations = (
        db.session.query(Reservation, ParkingLot)
        .join(ParkingSpot, Reservation.spot_id == ParkingSpot.id)
        .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id)
        .filter(Reservation.user_id == user_id)
        .all()
    )


    lot_times = {}
    for res, lot in reservations:
        if res.leaving_time:
            time_spent = (res.leaving_time - res.parking_time).total_seconds() / 3600  # hours
        else:
            time_spent = (datetime.utcnow() - res.parking_time).total_seconds() / 3600

        if lot.prime_location_name in lot_times:
            lot_times[lot.prime_location_name] += time_spent
        else:
            lot_times[lot.prime_location_name] = time_spent

    labels = list(lot_times.keys()) if lot_times else []
    data = [round(t, 2) for t in lot_times.values()] if lot_times else []


    return render_template('user_summary.html', labels=labels, data=data)

@app.route('/admin_summary')
def admin_summary():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    reservations = db.session.query(
        ParkingLot.prime_location_name,
        Reservation.parking_time,
        Reservation.leaving_time
    ).join(ParkingSpot, ParkingLot.id == ParkingSpot.lot_id)\
     .join(Reservation, Reservation.spot_id == ParkingSpot.id)\
     .filter(Reservation.leaving_time.isnot(None))\
     .all()

    lot_revenue = defaultdict(float)
    rate_per_hour = 50

    for lot_name, parking_time, leaving_time in reservations:
        duration = (leaving_time - parking_time).total_seconds() / 3600
        est_cost = math.ceil(duration) * rate_per_hour
        lot_revenue[lot_name] += est_cost

    lot_names = list(lot_revenue.keys())
    revenue_values = [round(lot_revenue[name], 2) for name in lot_names]

    lot_spot_counts = db.session.query(
        ParkingLot.prime_location_name,
        ParkingSpot.status,
        db.func.count(ParkingSpot.id)
    ).join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id)\
     .group_by(ParkingLot.prime_location_name, ParkingSpot.status)\
     .all()

    status_labels = list(set(lot_name for lot_name, _, _ in lot_spot_counts))
    available_counts, occupied_counts = [], []

    for lot_name in status_labels:
        available = sum(count for ln, status, count in lot_spot_counts if ln == lot_name and status == 'A')
        occupied = sum(count for ln, status, count in lot_spot_counts if ln == lot_name and status == 'O')
        available_counts.append(available)
        occupied_counts.append(occupied)

    lot_names = lot_names or []
    revenue_values = revenue_values or []
    status_labels = status_labels or []
    available_counts = available_counts or []
    occupied_counts = occupied_counts or []

    return render_template(
        'admin_summary.html',
        lot_names=lot_names,
        revenue_values=revenue_values,
        status_labels=status_labels,
        available_counts=available_counts,
        occupied_counts=occupied_counts
    )



@app.route('/logout')
def logout():
    flash("Logged out successfully!", 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        with db.session.begin_nested():
            if not User.query.filter_by(role='admin').first():
                admin = User(email="admin@app.com", password="admin123", role="admin")
                db.session.add(admin)
                print("✅ Default admin created!")

        db.session.commit()

    app.run(debug=True)

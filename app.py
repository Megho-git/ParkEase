from flask import Flask, render_template, request, redirect, url_for, flash
from models.models import db, User, ParkingLot, ParkingSpot, Reservation, RecentBooking

app = Flask(__name__)
app.secret_key = 'secret-key'

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Create tables if not exists
with app.app_context():
    db.create_all()
    if not ParkingLot.query.first():
        lot1 = ParkingLot(prime_location_name="City Center", address="12 MG Road, Kolkata", pin_code="700001", price_per_hour=50, available_spots=5)
        lot2 = ParkingLot(prime_location_name="Salt Lake Sector V", address="DLF IT Park, Kolkata", pin_code="700091", price_per_hour=40, available_spots=3)
        lot3 = ParkingLot(prime_location_name="South City", address="375 Prince Anwar Shah Road", pin_code="700068", price_per_hour=60, available_spots=7)

        db.session.add_all([lot1, lot2, lot3])
        db.session.commit()
        print("✅ Dummy parking lots seeded!")

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

        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            flash("Login successful!", 'success')
            return redirect(url_for('user_dashboard'))
        else:
            flash("Invalid email or password", 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/search_parking', methods=['GET'])
def search_parking():
    query = request.args.get('q')
    results = []

    if query:
        # Find lots where address or pincode matches query
        lots = ParkingLot.query.filter(
            (ParkingLot.address.ilike(f'%{query}%')) |
            (ParkingLot.pin_code.ilike(f'%{query}%'))
        ).all()

        # Check available spots count for each matching lot
        for lot in lots:
            available_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
            if available_spots > 0:
                results.append({
                    'lot_id': lot.id,
                    'address': lot.address,
                    'available_spots': available_spots
                })

    # Render the same user dashboard with search results
    return render_template('user_dashboard.html', results=results)

# User Dashboard route
@app.route('/dashboard')
def user_dashboard():
    location_query = request.args.get('location', '')

    if location_query:
        results = ParkingLot.query.filter(
            (ParkingLot.address.ilike(f"%{location_query}%")) |
            (ParkingLot.pin_code.ilike(f"%{location_query}%"))
        ).filter(ParkingLot.available_spots > 0).all()
    else:
        results = []

    return render_template('user_dashboard.html', results=results)


# Dummy Logout route (fix for your navbar link)
@app.route('/logout')
def logout():
    flash("Logged out successfully!", 'info')
    return redirect(url_for('login'))

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
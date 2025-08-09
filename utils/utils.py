import qrcode
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import os
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent 
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Debug print
print(f"Utils.py loading .env from: {env_path}")
print(f"SENDER_EMAIL in utils: {os.getenv('SENDER_EMAIL')}")

def generate_qr_image(data):
    """Generate QR code image and return as BytesIO buffer"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer
    except Exception as e:
        print(f"QR generation error: {e}")
        return None

def build_booking_email(user, lot, reservation_id, booking_datetime=None):
    """Build HTML email body for booking confirmation"""
    if booking_datetime:
        booking_time_str = booking_datetime.strftime("%B %d, %Y at %I:%M %p")
    else:
        booking_time_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
            <h2 style="color: #007bff;">🎉 Parking Spot Reserved!</h2>
            
            <h3>Hi {user.fullname},</h3>
            
            <p>Great news! Your parking spot has been successfully reserved.</p>
            
            <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="color: #007bff;">📍 Reservation Details:</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Location:</strong></td><td style="padding: 5px;">{lot.prime_location_name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Address:</strong></td><td style="padding: 5px;">{lot.address}, {lot.pin_code}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Rate:</strong></td><td style="padding: 5px;">₹{lot.price_per_hour}/hour</td></tr>
                    <tr><td style="padding: 5px;"><strong>Scheduled Time:</strong></td><td style="padding: 5px;"><strong>{booking_time_str}</strong></td></tr>
                    <tr><td style="padding: 5px;"><strong>Reservation ID:</strong></td><td style="padding: 5px;">{reservation_id}</td></tr>
                </table>
            </div>
            
            <h4 style="color: #007bff;">🔍 Your Entry QR Code</h4>
            <p><strong>Present this QR code when you arrive at the scheduled time:</strong></p>
            
            <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="color: #007bff;">📋 Important Instructions:</h4>
                <ul>
                    <li><strong>Arrival Time</strong> - Arrive at your scheduled time: {booking_time_str}</li>
                    <li><strong>QR Code Required</strong> - Present this QR code to the attendant</li>
                    <li><strong>Early Cancellation</strong> - Cancel before scheduled time: 25% minimum charge</li>
                    <li><strong>Late Arrival</strong> - Full hourly rates apply after scheduled time</li>
                    <li><strong>Support</strong> - Contact us immediately if you face any issues</li>
                </ul>
            </div>
            
            <p>Thank you for choosing <strong>ParkEase</strong>! Your spot is waiting for you. 🅿️</p>
            
            <p style="font-size: 12px; color: #666;">
                <em>Need help? Reply to this email or contact our support team.</em>
            </p>
        </div>
    </body>
    </html>
    """
    
    return html_body

def send_email_with_qr(to_email, subject, html_body, qr_buffer):
    """Send email with QR code attachment"""
    try:
        smtp_server = os.getenv('SMTP_SERVER', 'smtp-relay.brevo.com')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        sender_email = os.getenv('SENDER_EMAIL')  
        brevo_login = os.getenv('BREVO_LOGIN')    
        sender_password = os.getenv('SENDER_PASSWORD')  
        
        print(f"=== EMAIL DEBUG ===")
        print(f"SMTP Server: {smtp_server}")
        print(f"Port: {smtp_port}")
        print(f"From (Display): {sender_email}")
        print(f"Login Username: {brevo_login}")
        print(f"Password set: {'Yes' if sender_password else 'No'}")
        
        if not all([sender_email, brevo_login, sender_password]):
            print("ERROR: Email credentials missing")
            return False, "Email credentials not configured"
        
        msg = MIMEMultipart('related')
        msg['From'] = sender_email  
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(html_body, 'html'))
        
        if qr_buffer:
            qr_buffer.seek(0)
            qr_image = MIMEImage(qr_buffer.read())
            qr_image.add_header('Content-ID', '<qr_code>')
            qr_image.add_header('Content-Disposition', 'attachment', filename='qr_code.png')
            msg.attach(qr_image)
        
        print("Connecting to SMTP server...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        
        print("Logging in...")
        server.login(brevo_login, sender_password)  
        
        print("Sending email...")
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)  
        server.quit()
        
        print("Email sent successfully!")
        return True, "Email sent successfully"
        
    except Exception as e:
        error_msg = f"Email error: {str(e)} (Type: {type(e).__name__})"
        print(error_msg)
        return False, error_msg
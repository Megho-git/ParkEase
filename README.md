<h1>ParkEase — Smart Parking Management System</h1>

<h2>Overview</h2>

<p>
ParkEase is a web-based parking management platform designed to streamline reservation, monitoring,
and billing workflows through automated booking, real-time status tracking, and QR-based access control.
Built using Flask and modern web technologies, it serves both parking administrators and end-users through
a responsive and intuitive interface.
</p>


<h2>Key Features</h2>

<h3>For Users</h3>

<ul>
  <li><strong>Smart Booking System:</strong> Schedule parking with precise date/time selection and vehicle registration</li>
  <li><strong>QR Code Integration:</strong> Secure entry verification via QR codes delivered through email</li>
  <li><strong>Flexible Cancellation:</strong> Dynamic pricing based on cancellation timing and policy rules</li>
  <li><strong>Real-Time Dashboards:</strong> View active reservations, usage history, and cost summaries</li>
  <li><strong>Mobile-Responsive Design:</strong> Optimized interface with progressive validation across devices</li>
</ul>


<h3>For Administrators</h3>

<ul>
  <li><strong>Multi-Lot Management:</strong> Create, configure, and monitor multiple parking facilities</li>
  <li><strong>User Search & Analytics:</strong> Search users and inspect detailed reservation records</li>
  <li><strong>QR Scanner Interface:</strong> Camera-based verification for spot release and access control</li>
  <li><strong>Revenue Analytics:</strong> Reporting on usage trends and financial performance</li>
  <li><strong>Advanced Controls:</strong> Business-rule enforcement for occupied spot and lot management</li>
</ul>


<h2>Technology Stack</h2>

<ul>
  <li><strong>Backend:</strong> Python, Flask, SQLAlchemy ORM, SQLite</li>
  <li><strong>Frontend:</strong> HTML5, CSS3, JavaScript (Vanilla), Responsive UI</li>
  <li><strong>Email Service:</strong> Brevo SMTP with automated QR code delivery</li>
  <li><strong>Security:</strong> Role-based access control, session handling, input validation</li>
</ul>


<h2>Architecture Highlights</h2>

<ul>
  <li><strong>Time-Based Pricing Logic:</strong> Accurate billing based on scheduled and actual parking duration</li>
  <li><strong>Real-Time Status Management:</strong> Dynamic spot allocation and availability updates</li>
  <li><strong>Modular Design:</strong> Clear separation of models, utilities, views, and templates</li>
  <li><strong>Progressive Enhancement:</strong> Graceful degradation and accessibility-aware interface design</li>
</ul>


<h2>System Capabilities</h2>

<ul>
  <li>Automated reservation lifecycle management</li>
  <li>Integrated QR-based authentication workflow</li>
  <li>Email-driven confirmation and cancellation system</li>
  <li>Real-time synchronization between user and admin views</li>
  <li>Scalable multi-location architecture</li>
</ul>


<h2>Design Principles</h2>

<ul>
  <li>Reliability through transactional consistency</li>
  <li>Security-first access control</li>
  <li>User-centric interface design</li>
  <li>Maintainable modular codebase</li>
  <li>Clear separation of business logic and presentation</li>
</ul>


<h2>Limitations</h2>

<ul>
  <li>Currently optimized for small to medium parking facilities</li>
  <li>Uses SQLite for development and prototyping</li>
  <li>Requires external SMTP configuration for email delivery</li>
  <li>Does not include automated payment gateway integration</li>
</ul>


<h2>Intended Use</h2>

<p>
ParkEase is designed as an academic and applied software engineering project demonstrating full-stack
system design, backend automation, and real-world workflow modeling. It may be extended for production
use with additional scaling and security enhancements.
</p>


<h2>Disclaimer</h2>

<p>
This system is provided for educational and demonstration purposes. It is not intended for direct
deployment in critical commercial environments without further validation and security auditing.
</p>

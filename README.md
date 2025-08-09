ParkEase - Smart Parking Management System
Overview
ParkEase is a comprehensive web-based parking management platform that streamlines parking operations through intelligent booking, real-time monitoring, and automated billing. Built with Flask and modern web technologies, it serves both parking administrators and end-users with a seamless, responsive interface.

Key Features
For Users
Smart Booking System - Schedule parking with precise date/time selection and vehicle registration

QR Code Integration - Secure entry verification through generated QR codes sent via email

Flexible Cancellation - Dynamic pricing based on cancellation timing (25% fee for early cancellation, full rate after scheduled time)

Real-time Dashboards - Track active reservations, usage history, and cost summaries

Mobile-Responsive Design - Optimized for all devices with progressive form validation

For Administrators
Multi-Lot Management - Create, edit, and monitor multiple parking locations

User Search & Analytics - Search users by ID/name and view detailed reservation data

QR Scanner Interface - Camera-based QR scanning for spot release verification

Revenue Analytics - Comprehensive reporting on usage patterns and financial metrics

Advanced Controls - Prevent deletion of occupied spots/lots with business logic enforcement

Technology Stack
Backend: Python Flask, SQLAlchemy ORM, SQLite Database

Frontend: HTML5, CSS3, JavaScript (Vanilla), Responsive Design

Email Service: Brevo SMTP integration with QR code attachments

Security: Role-based access control, session management, input validation

Architecture Highlights
Time-based Pricing Logic - Sophisticated calculations handling scheduled vs. actual parking duration

Real-time Status Updates - Dynamic spot availability and reservation management

Modular Design - Separation of concerns with dedicated models, utils, and templates

Progressive Enhancement - Graceful degradation with accessibility considerations

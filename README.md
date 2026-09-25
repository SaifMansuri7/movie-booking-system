# Movie Booking System — Backend API

A Django REST Framework backend for a movie ticket booking platform, built to explore real-world backend engineering concerns: authentication, authorization, race conditions, and API design — not just CRUD.

## Features

- **Authentication**: Signup with email OTP verification, JWT-based login (access + refresh tokens)
- **Role-based access control**: Admin-only endpoints for managing movies, theatres, shows, and seats
- **Seat locking with expiry**: Seats can be temporarily locked (5 minutes) before booking, preventing two users from booking the same seat
- **Race condition safe booking**: Uses database row-level locking (`select_for_update`) and atomic transactions to prevent double-booking under concurrent requests
- **Booking ownership security**: Only the user who locked a seat can confirm the booking for it — enforced at the database level, not just the UI
- **Third-party API integration**: Fetch movie details from TMDB (The Movie Database) with timeout and error handling
- **Automated tests**: 20 tests covering signup, OTP, login, permissions, seat locking, booking confirmation (including the ownership-security case), and mocked TMDB integration
- **Interactive API documentation**: Swagger UI and Redoc, auto-generated from the codebase

## Tech Stack

- **Backend**: Django, Django REST Framework
- **Authentication**: djangorestframework-simplejwt (JWT)
- **Database**: SQLite (development)
- **API Docs**: drf-spectacular (OpenAPI 3.0)
- **Testing**: Django's built-in test framework, `unittest.mock` for external API mocking

## Setup

1. Clone the repository

git clone <repo-url>
cd movie-booking-system


2. Create and activate a virtual environment

python -m venv venv
venv\Scripts\activate # Windows
source venv/bin/activate # macOS/Linux


3. Install dependencies

pip install -r requirements.txt


4. Create a `.env` file in the project root with:

TMDB_API_KEY=your_tmdb_api_key_here


5. Run migrations

python manage.py migrate


6. Start the server

python manage.py runserver


7. API documentation is available at `http://127.0.0.1:8000/api/docs/`

## Running Tests

python manage.py test


## Key Design Decisions

- **Why seat locking instead of direct booking?** Prevents two users from simultaneously booking the same seat by giving one user a temporary (5-minute) hold before final confirmation.
- **Why `select_for_update()` and `transaction.atomic()`?** Without database-level row locking, two nearly-simultaneous requests could both read a seat as available before either writes their update — a classic TOCTOU (time-of-check-to-time-of-use) race condition. Locking the row for the duration of the transaction closes this gap.
- **Why track `locked_by` on a seat?** Without recording *who* locked a seat, any authenticated user could confirm a booking on a seat someone else locked — a broken access control vulnerability. This field, combined with an ownership check in the confirm-booking view, closes that gap.
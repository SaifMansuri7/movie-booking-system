from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import requests
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import OTP, Movie, Theatre, Show, Seat, Booking

User = get_user_model()


class SignupTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.signup_url = '/api/signup/'

    def test_signup_creates_user_and_otp(self):
        data = {
            "username": "rahul123",
            "email": "rahul@example.com",
            "password": "StrongPass123",
            "phone_number": "+919876543210",
            "age": 25
        }
        response = self.client.post(self.signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="rahul123").exists())
        user = User.objects.get(username="rahul123")
        self.assertFalse(user.is_verified)
        self.assertTrue(OTP.objects.filter(user=user).exists())

    def test_duplicate_username_signup_fails(self):
        User.objects.create_user(
            username="rahul123",
            email="rahul@example.com",
            password="StrongPass123",
            phone_number="+919876543210",
            age=25
        )
        data = {
            "username": "rahul123",
            "email": "rahul_new@example.com",
            "password": "AnotherPass123",
            "phone_number": "+919876543211",
            "age": 30
        }
        response = self.client.post(self.signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(username="rahul123").count(), 1)


class OTPVerificationTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.verify_url = '/api/verify-otp/'
        self.user = User.objects.create_user(
            username="testuser6",
            email="testuser6@test.com",
            password="testpass333",
            phone_number="1111111111",
            age=22
        )

    def test_correct_otp_verifies_user(self):
        otp = OTP.objects.create(
            user=self.user,
            otp_code="808499",
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        data = {"email": "testuser6@test.com", "otp_code": "808499"}
        response = self.client.post(self.verify_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_wrong_otp_fails(self):
        OTP.objects.create(
            user=self.user,
            otp_code="808499",
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        data = {"email": "testuser6@test.com", "otp_code": "999999"}
        response = self.client.post(self.verify_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)

    def test_expired_otp_fails(self):
        OTP.objects.create(
            user=self.user,
            otp_code="808499",
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        data = {"email": "testuser6@test.com", "otp_code": "808499"}
        response = self.client.post(self.verify_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)


class LoginTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.login_url = '/api/login/'

    def test_unverified_user_cannot_login(self):
        User.objects.create_user(
            username="testuser4",
            email="testuser4@test.com",
            password="testpass111",
            phone_number="2222222222",
            age=24
        )
        data = {"username": "testuser4", "password": "testpass111"}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('access', response.data)

    def test_verified_user_can_login(self):
        user = User.objects.create_user(
            username="testuser4",
            email="testuser4@test.com",
            password="testpass111",
            phone_number="2222222222",
            age=24
        )
        user.is_verified = True
        user.save()

        data = {"username": "testuser4", "password": "testpass111"}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)


class MoviePermissionTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.movie_url = '/api/movies/'

        self.admin_user = User.objects.create_user(
            username="admin1",
            email="admin1@test.com",
            password="adminpass123",
            phone_number="3333333333",
            age=30,
            role='admin',
            is_verified=True
        )

        self.customer_user = User.objects.create_user(
            username="customer1",
            email="customer1@test.com",
            password="custpass123",
            phone_number="4444444444",
            age=28,
            role='customer',
            is_verified=True
        )

        self.movie_data = {
            "title": "Avengers: Endgame",
            "genre": "Action",
            "description": "The Avengers face their greatest challenge.",
            "poster_url": "https://example.com/avengers-endgame.jpg",
            "duration": 181,
            "age_rating": "UA"
        }

    def test_admin_can_create_movie(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.movie_url, self.movie_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Movie.objects.filter(title="Avengers: Endgame").exists())

    def test_customer_cannot_create_movie(self):
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(self.movie_url, self.movie_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Movie.objects.count(), 0)

    def test_unauthenticated_user_cannot_create_movie(self):
        response = self.client.post(self.movie_url, self.movie_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Movie.objects.count(), 0)

    def test_anyone_can_list_movies(self):
        Movie.objects.create(**self.movie_data)
        response = self.client.get(self.movie_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class SeatLockingAndBookingTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.lock_url = '/api/seats/lock/'
        self.confirm_url = '/api/bookings/confirm/'

        self.user_a = User.objects.create_user(
            username="usera",
            email="usera@test.com",
            password="passA12345",
            phone_number="5555555555",
            age=26,
            is_verified=True
        )

        self.user_b = User.objects.create_user(
            username="userb",
            email="userb@test.com",
            password="passB12345",
            phone_number="6666666666",
            age=27,
            is_verified=True
        )

        movie = Movie.objects.create(
            title="Avengers: Endgame",
            genre="Action",
            description="The Avengers face their greatest challenge.",
            poster_url="https://example.com/avengers-endgame.jpg",
            duration=181,
            age_rating="UA"
        )

        theatre = Theatre.objects.create(
            name="PVR Cinemas",
            city="Mumbai",
            latitude=19.0760,
            longitude=72.8777
        )

        self.show = Show.objects.create(
            movie=movie,
            theatre=theatre,
            show_datetime=timezone.now() + timedelta(days=1),
            price=250.00
        )

        self.seat = Seat.objects.create(
            show=self.show,
            seat_number="A1",
            status='available'
        )

    def test_user_can_lock_available_seat(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.lock_url, {"seat_id": self.seat.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.seat.refresh_from_db()
        self.assertEqual(self.seat.status, 'locked')
        self.assertEqual(self.seat.locked_by_id, self.user_a.id)

    def test_cannot_lock_already_booked_seat(self):
        self.seat.status = 'booked'
        self.seat.save()

        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.lock_url, {"seat_id": self.seat.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_second_user_cannot_lock_seat_already_locked_by_first_user(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.lock_url, {"seat_id": self.seat.id}, format='json')

        self.client.force_authenticate(user=self.user_b)
        response = self.client.post(self.lock_url, {"seat_id": self.seat.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_confirm_their_own_locked_seat(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.lock_url, {"seat_id": self.seat.id}, format='json')

        response = self.client.post(
            self.confirm_url,
            {"show_id": self.show.id, "seat_ids": [self.seat.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.seat.refresh_from_db()
        self.assertEqual(self.seat.status, 'booked')
        self.assertTrue(Booking.objects.filter(user=self.user_a, show=self.show).exists())

    def test_confirming_unlocked_seat_fails(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(
            self.confirm_url,
            {"show_id": self.show.id, "seat_ids": [self.seat.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Booking.objects.count(), 0)

    def test_other_user_cannot_confirm_someone_elses_locked_seat(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.lock_url, {"seat_id": self.seat.id}, format='json')

        self.client.force_authenticate(user=self.user_b)
        response = self.client.post(
            self.confirm_url,
            {"show_id": self.show.id, "seat_ids": [self.seat.id]},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Booking.objects.filter(user=self.user_b).count(), 0)
        self.seat.refresh_from_db()
        self.assertEqual(self.seat.status, 'locked')
        self.assertEqual(self.seat.locked_by_id, self.user_a.id)


class TMDBIntegrationTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.fetch_url = '/api/movies/fetch-tmdb/'

        self.admin_user = User.objects.create_user(
            username="admin2",
            email="admin2@test.com",
            password="adminpass456",
            phone_number="7777777777",
            age=32,
            role='admin',
            is_verified=True
        )
        self.client.force_authenticate(user=self.admin_user)

    @patch('booking.utils.requests.get')
    def test_fetch_movie_success(self, mock_get):
        # Arrange - fake TMDB response taiyar kiya
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "results": [
                {
                    "title": "Inception",
                    "overview": "A thief who steals corporate secrets through dream-sharing technology.",
                    "poster_path": "/inception.jpg"
                }
            ]
        }
        mock_get.return_value = fake_response

        # Act
        response = self.client.post(self.fetch_url, {"title": "Inception"}, format='json')

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Movie.objects.filter(title="Inception").exists())

    @patch('booking.utils.requests.get')
    def test_fetch_movie_not_found_on_tmdb(self, mock_get):
        fake_response = MagicMock()
        fake_response.json.return_value = {"results": []}
        mock_get.return_value = fake_response

        response = self.client.post(self.fetch_url, {"title": "SomeNonExistentMovie"}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Movie.objects.count(), 0)

    @patch('booking.utils.requests.get')
    def test_fetch_movie_handles_network_error(self, mock_get):
        # TMDB tak pahunch hi nahi paaye, jaise network down ho
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = self.client.post(self.fetch_url, {"title": "Inception"}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Movie.objects.count(), 0)
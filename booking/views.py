from rest_framework.views import APIView
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer
from .models import Movie, Theatre, Show, Seat, Booking, BookingSeat
from .serializers import (
    UserSignupSerializer,
    OTPVerifySerializer,
    CustomTokenObtainPairSerializer,
    MovieSerializer,
    TheatreSerializer,
    ShowSerializer,
    SeatSerializer,
    BookingCreateSerializer,
    BookingSerializer,
)
from .utils import generate_otp, fetch_movie_from_tmdb


class SignupView(APIView):
    @extend_schema(request=UserSignupSerializer)
    def post(self, request):
        serializer = UserSignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            generate_otp(user)
            return Response({"message": "Signup successful. OTP sent to your email."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    @extend_schema(request=OTPVerifySerializer)
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp = serializer.validated_data['otp']

            user.is_verified = True
            user.save()

            otp.is_used = True
            otp.save()

            return Response({"message": "Account verified successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == 'admin'


class MovieListCreateView(generics.ListCreateAPIView):
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    permission_classes = [IsAdminOrReadOnly]


class TheatreListCreateView(generics.ListCreateAPIView):
    queryset = Theatre.objects.all()
    serializer_class = TheatreSerializer
    permission_classes = [IsAdminOrReadOnly]


class ShowListCreateView(generics.ListCreateAPIView):
    queryset = Show.objects.all()
    serializer_class = ShowSerializer
    permission_classes = [IsAdminOrReadOnly]


class BulkSeatCreateView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    @extend_schema(
        request=inline_serializer(
            name='BulkSeatCreateRequest',
            fields={
                'show_id': serializers.IntegerField(),
                'rows': serializers.ListField(child=serializers.CharField()),
                'seats_per_row': serializers.IntegerField(),
            }
        )
    )
    def post(self, request):
        show_id = request.data.get('show_id')
        rows = request.data.get('rows')
        seats_per_row = request.data.get('seats_per_row')

        try:
            show = Show.objects.get(id=show_id)
        except Show.DoesNotExist:
            return Response({"error": "Show not found."}, status=status.HTTP_404_NOT_FOUND)

        created_seats = []
        for row_letter in rows:
            for seat_num in range(1, seats_per_row + 1):
                seat = Seat.objects.create(
                    show=show,
                    seat_number=f"{row_letter}{seat_num}",
                    status='available'
                )
                created_seats.append(seat.seat_number)

        return Response({"message": f"{len(created_seats)} seats created.", "seats": created_seats}, status=status.HTTP_201_CREATED)


class SeatListView(generics.ListAPIView):
    serializer_class = SeatSerializer

    def get_queryset(self):
        show_id = self.request.query_params.get('show_id')

        # Lazily release any seat whose 5-minute lock has expired. There is no
        # background job doing this, so we sweep for stale locks every time
        # anyone (including the frontend's polling) asks for this show's seats.
        # This means a seat abandoned mid-booking (e.g. the user's connection
        # drops) becomes visibly 'available' again on its own, without
        # requiring another user to actively retry locking it first.
        expiry_cutoff = timezone.now() - timedelta(minutes=5)
        Seat.objects.filter(
            show_id=show_id,
            status='locked',
            locked_at__lt=expiry_cutoff,
        ).update(status='available', locked_at=None, locked_by=None)

        return Seat.objects.filter(show_id=show_id)


class LockSeatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name='LockSeatRequest',
            fields={'seat_id': serializers.IntegerField()}
        )
    )
    def post(self, request):
        seat_id = request.data.get('seat_id')

        with transaction.atomic():
            try:
                seat = Seat.objects.select_for_update().get(id=seat_id)
            except Seat.DoesNotExist:
                return Response({"error": "Seat not found."}, status=status.HTTP_404_NOT_FOUND)

            if seat.status == 'booked':
                return Response({"error": "Seat already booked."}, status=status.HTTP_400_BAD_REQUEST)

            if seat.status == 'locked':
                lock_expired = seat.locked_at and timezone.now() >= seat.locked_at + timedelta(minutes=5)
                if not lock_expired and seat.locked_by_id != request.user.id:
                    return Response({"error": "Seat is currently locked by another user."}, status=status.HTTP_400_BAD_REQUEST)

            seat.status = 'locked'
            seat.locked_at = timezone.now()
            seat.locked_by = request.user
            seat.save()

        return Response({"message": f"Seat {seat.seat_number} locked for 5 minutes."}, status=status.HTTP_200_OK)


class ConfirmBookingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=BookingCreateSerializer)
    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        show_id = serializer.validated_data['show_id']
        seat_ids = serializer.validated_data['seat_ids']

        try:
            show = Show.objects.get(id=show_id)
        except Show.DoesNotExist:
            return Response({"error": "Show not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            seats = Seat.objects.select_for_update().filter(id__in=seat_ids, show=show)

            if seats.count() != len(seat_ids):
                return Response({"error": "One or more seats not found for this show."}, status=status.HTTP_400_BAD_REQUEST)

            for seat in seats:
                if seat.status != 'locked':
                    return Response({"error": f"Seat {seat.seat_number} is not locked and cannot be booked."}, status=status.HTTP_400_BAD_REQUEST)
                if seat.locked_by_id != request.user.id:
                    return Response({"error": f"Seat {seat.seat_number} was locked by another user."}, status=status.HTTP_403_FORBIDDEN)

            booking = Booking.objects.create(user=request.user, show=show, status='confirmed')

            for seat in seats:
                BookingSeat.objects.create(booking=booking, seat=seat)
                seat.status = 'booked'
                seat.save()

        return Response({"message": "Booking confirmed.", "booking_id": booking.id, "seats": [s.seat_number for s in seats]}, status=status.HTTP_201_CREATED)


class MyBookingsView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)


class CancelBookingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name='CancelBookingRequest',
            fields={'booking_id': serializers.IntegerField()}
        )
    )
    def post(self, request):
        booking_id = request.data.get('booking_id')

        try:
            booking = Booking.objects.get(id=booking_id, user=request.user)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        if booking.status == 'cancelled':
            return Response({"error": "Booking is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            seat_ids = BookingSeat.objects.filter(booking=booking).values_list('seat_id', flat=True)
            Seat.objects.select_for_update().filter(id__in=seat_ids).update(
                status='available', locked_at=None, locked_by=None
            )
            booking.status = 'cancelled'
            booking.save()

        return Response({"message": "Booking cancelled successfully."}, status=status.HTTP_200_OK)


class FetchMovieFromTMDBView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    @extend_schema(
        request=inline_serializer(
            name='FetchMovieFromTMDBRequest',
            fields={'title': serializers.CharField()}
        )
    )
    def post(self, request):
        title = request.data.get('title')

        if not title:
            return Response({"error": "Title is required."}, status=status.HTTP_400_BAD_REQUEST)

        movie_data = fetch_movie_from_tmdb(title)

        if not movie_data:
            return Response({"error": "Movie not found on TMDB."}, status=status.HTTP_404_NOT_FOUND)

        movie = Movie.objects.create(**movie_data)

        return Response({"message": "Movie added from TMDB.", "movie": MovieSerializer(movie).data}, status=status.HTTP_201_CREATED)
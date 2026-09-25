from django.urls import path
from .views import (
    SignupView,
    VerifyOTPView,
    MovieListCreateView,
    TheatreListCreateView,
    ShowListCreateView,
    BulkSeatCreateView,
    SeatListView,
    LockSeatView,
    ConfirmBookingView,
    MyBookingsView,
    FetchMovieFromTMDBView,
)

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('movies/', MovieListCreateView.as_view(), name='movie-list-create'),
    path('theatres/', TheatreListCreateView.as_view(), name='theatre-list-create'),
    path('shows/', ShowListCreateView.as_view(), name='show-list-create'),
    path('seats/bulk-create/', BulkSeatCreateView.as_view(), name='seat-bulk-create'),
    path('seats/', SeatListView.as_view(), name='seat-list'),
    path('seats/lock/', LockSeatView.as_view(), name='seat-lock'),
    path('bookings/confirm/', ConfirmBookingView.as_view(), name='booking-confirm'),
    path('bookings/my/', MyBookingsView.as_view(), name='my-bookings'),
    path('movies/fetch-tmdb/', FetchMovieFromTMDBView.as_view(), name='fetch-movie-tmdb'),
]
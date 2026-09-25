import random
import requests
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import OTP
import socket
import urllib3.util.connection as urllib3_cn


def allowed_gai_family():
    return socket.AF_INET


urllib3_cn.allowed_gai_family = allowed_gai_family


def generate_otp(user):
    otp_code = str(random.randint(100000, 999999))
    expiry_time = timezone.now() + timedelta(minutes=5)

    OTP.objects.create(
        user=user,
        otp_code=otp_code,
        expires_at=expiry_time
    )

    send_mail(
        'Your OTP Code',
        f'Your OTP is {otp_code}. It expires in 5 minutes.',
        'noreply@moviebooking.com',
        [user.email],
    )


def fetch_movie_from_tmdb(title):
    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        'api_key': settings.TMDB_API_KEY,
        'query': title
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    if not data.get('results'):
        return None

    movie_data = data['results'][0]

    return {
        'title': movie_data.get('title'),
        'description': movie_data.get('overview'),
        'poster_url': f"https://image.tmdb.org/t/p/w500{movie_data.get('poster_path')}",
        'genre': 'Unknown',
        'duration': 120,
        'age_rating': 'UA',
    }
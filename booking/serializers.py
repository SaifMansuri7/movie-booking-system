from rest_framework import serializers
from django.utils import timezone
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, OTP, Movie, Theatre, Show, Seat, Booking, BookingSeat


class UserSignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'age', 'password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)

    def validate(self, data):
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        try:
            otp = OTP.objects.filter(user=user, otp_code=data['otp_code'], is_used=False).latest('created_at')
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")

        if otp.expires_at < timezone.now():
            raise serializers.ValidationError("OTP has expired.")

        data['user'] = user
        data['otp'] = otp
        return data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        if not self.user.is_verified:
            raise serializers.ValidationError("Account not verified. Please verify OTP first.")

        return data


class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'


class TheatreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theatre
        fields = '__all__'


class ShowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Show
        fields = '__all__'


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = '__all__'


class BookingCreateSerializer(serializers.Serializer):
    show_id = serializers.IntegerField()
    seat_ids = serializers.ListField(child=serializers.IntegerField())

class BookingSerializer(serializers.ModelSerializer):
    show = ShowSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'show', 'status', 'booked_at']
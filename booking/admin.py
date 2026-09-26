from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Movie, Theatre, Show, Seat, Booking, BookingSeat, OTP


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('phone_number', 'age', 'role', 'is_verified')}),
    )
    list_display = ('username', 'email', 'role', 'is_verified', 'is_staff')


admin.site.register(User, CustomUserAdmin)
admin.site.register(Movie)
admin.site.register(Theatre)
admin.site.register(Show)
admin.site.register(Seat)
admin.site.register(Booking)
admin.site.register(BookingSeat)
admin.site.register(OTP)
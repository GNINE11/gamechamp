from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
# Register your models here.

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ist_display = ("username", "email", "ranking_score", "created_at", "is_staff", "is_active")
    search_fields = ("username", "email")
    list_filter = ("is_staff", "is_active")
    readonly_fields = ("created_at",)

    # Adiciona os campos customizados na página de EDIÇÃO do usuário existente
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Perfil", {
            "fields": ("avatar", "bio", "ranking_score")
        }),
        ("Datas", {
            "fields": ("created_at",)
        }),
    )

    # Adiciona os campos customizados na página de CRIAÇÃO de novo usuário
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Perfil", {
            "fields": ("avatar", "bio", "ranking_score")
        }),
    )
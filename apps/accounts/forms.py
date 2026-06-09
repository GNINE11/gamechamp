from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class SignupForm(forms.Form):
    full_name        = forms.CharField(max_length=150, label="Nome Completo")
    username         = forms.CharField(max_length=150, label="Nome de Usuário")
    email            = forms.EmailField(label="Email")
    password         = forms.CharField(widget=forms.PasswordInput, label="Senha")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirmar Senha")

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise ValidationError("Este e-mail já está cadastrado.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error("confirm_password", "As senhas não coincidem.")
        return cleaned

    def save(self):
        data       = self.cleaned_data
        full_name  = data["full_name"].split(" ", 1)
        first_name = full_name[0]
        last_name  = full_name[1] if len(full_name) > 1 else ""
        user = User.objects.create_user(
            username   = data["username"],
            email      = data["email"],
            password   = data["password"],
            first_name = first_name,
            last_name  = last_name,
        )
        return user


class EditProfileForm(forms.Form):
    full_name        = forms.CharField(max_length=150, required=False)
    username         = forms.CharField(max_length=150)
    email            = forms.EmailField()
    bio              = forms.CharField(widget=forms.Textarea, required=False)
    avatar           = forms.ImageField(required=False)
    current_password = forms.CharField(widget=forms.PasswordInput, required=False)
    new_password     = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_new_password = forms.CharField(widget=forms.PasswordInput, required=False)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exclude(pk=self.user.pk).exists():
            raise ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("Este e-mail já está em uso.")
        return email

    def clean(self):
        cleaned = super().clean()
        current  = cleaned.get("current_password")
        new_p    = cleaned.get("new_password")
        confirm  = cleaned.get("confirm_new_password")

        # Só valida senha se o usuário preencheu algo
        if current or new_p or confirm:
            if not self.user.check_password(current):
                self.add_error("current_password", "Senha atual incorreta.")
            if new_p != confirm:
                self.add_error("confirm_new_password", "As senhas não coincidem.")
            if new_p:
                try:
                    validate_password(new_p, self.user)
                except ValidationError as e:
                    self.add_error("new_password", e)
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = self.user

        # Atualiza nome
        full_name  = data.get("full_name", "").split(" ", 1)
        user.first_name = full_name[0]
        user.last_name  = full_name[1] if len(full_name) > 1 else ""
        user.username   = data["username"]
        user.email      = data["email"]
        user.bio        = data.get("bio", "")

        if data.get("avatar"):
            user.avatar = data["avatar"]

        if data.get("new_password"):
            user.set_password(data["new_password"])

        user.save()
        return user
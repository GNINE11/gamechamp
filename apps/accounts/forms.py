import re
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

def add_attr(field, attr_name, attr_new_val):
    existing = field.widget.attrs.get(attr_name, '')
    field.widget.attrs[attr_name] = f'{existing} {attr_new_val}'.strip()


def add_placeholder(field, placeholder_val):
    add_attr(field, 'placeholder', placeholder_val)


def strong_password(password):
    regex = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9]).{8,}$')

    if not regex.match(password):
        raise ValidationError((
            'A senha deve conter pelo menos uma letra maiúscula, '
            'uma letra minúscula e um número. O tamanho deve ser de '
            'deve ser de pelo menos 8 caracteres.'
        ),
            code='invalid'
        )



class SignupForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_placeholder(self.fields["first_name"], "Digite seu primeiro nome")
        add_placeholder(self.fields["last_name"], "Digite seu último nome")
        add_placeholder(self.fields["username"], "Digite um nome de usuário")
        add_placeholder(self.fields["email"], "email@exemplo.com"),
        add_placeholder(self.fields["password"], "Digite sua senha")
        add_placeholder(self.fields["confirm_password"], "Confirme sua senha")


    first_name = forms.CharField(
        widget = forms.TextInput(attrs={
            "class": "auth-input",
        }),
        error_messages={'required': 'Insira seu primeiro nome'},
        label= 'Primeiro nome'
    )

    last_name = forms.CharField(
         widget = forms.TextInput(attrs={
            "class": "auth-input",
        }),
        error_messages={'required': 'Insira seu último nome'},
        label='Último nome'
    )

    username = forms.CharField(
        widget = forms.TextInput(attrs={
            "class": "auth-input",
        }),
        error_messages={
            'required': 'Insira um nome de usuário',
            "min_length": "O nome de usuário deve ter pelo menos 4 caracteres",
            "max_length": "O nome de usuário deve ter no máximo 150 caracteres",
        },
        label= 'Nome de usuário',
        min_length=4, max_length=150,
    )

    email = forms.EmailField(
        widget = forms.TextInput(attrs={
            "class": "auth-input",
        }),
        
        error_messages={'required': 'Insira um e-mail',
                        'invalid': 'Digite um endereço de e-mail válido.'
        },
        label='E-mail',
    )

    password = forms.CharField(
        widget = forms.PasswordInput(attrs={
            "class": "auth-input",
        }),
        error_messages={
            'required': 'Insira uma senha'
        },
        help_text=(
            'A senha deve conter pelo menos uma letra maiúscula, '
            'uma letra minúscula e um número. O tamanho deve ser de '
            'deve ser de pelo menos 8 caracteres.'
        ),
        validators=[strong_password],
        label='Senha'
    )

    confirm_password = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(attrs={
            "class": "auth-input",
        }),
        error_messages={
            'required': 'Confirme sua senha'
        },
    )

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'password',
            'confirm_password'
        ]

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
        if p1:
            try:
                validate_password(p1)
            except ValidationError as e:
                self.add_error("password", e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):

    username = forms.CharField(
        label="Email ou Usuário",
        widget=forms.TextInput(attrs={
            "class": "auth-input",
            "placeholder": "commander@gamechamp.gg"
        }),
        error_messages={
            "required": "Informe seu usuário ou e-mail."
        }
    )

    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            "class": "auth-input",
            "placeholder": "Digite sua senha"
        }),
        error_messages={
            "required": "Informe sua senha."
        }
    )

class EditProfileForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "auth-input"}),
        required=False,
        label="Nova Senha",
        validators=[strong_password],
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "auth-input"}),
        required=False,
        label="Confirmar nova senha",
    )
    bio = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "auth-input",
            "rows": 3,
        }),
        required=False,
        label="Biografia",
    )
 
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "auth-input",
        }),
        required=False,
        label="Senha atual",
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "username",
            "email",
            "bio",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "auth-input"}),
            "last_name": forms.TextInput(attrs={"class": "auth-input"}),
            "username": forms.TextInput(attrs={"class": "auth-input"}),
            "email": forms.TextInput(attrs={"class": "auth-input"}),
        }

    def __init__(self, user, *args, **kwargs):
        self.user = user
        kwargs.setdefault("instance", user)
        super().__init__(*args, **kwargs)

        add_placeholder(self.fields["first_name"], "Digite seu primeiro nome")
        add_placeholder(self.fields["last_name"], "Digite seu último nome")
        add_placeholder(self.fields["username"], "Digite um nome de usuário")
        add_placeholder(self.fields["email"], "email@exemplo.com")
        add_placeholder(self.fields["bio"], "Fale um pouco sobre você...")
        add_placeholder(self.fields["current_password"], "Digite sua senha atual")

    # ── Validações de unicidade excluindo o próprio usuário ─────────────────
 
    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()

        if not username:
            raise ValidationError("Insira um nome de usuário.")

        if username == self.user.username:
            return self.user.username

        if User.objects.filter(username=username).exclude(pk=self.user.pk).exists():
            raise ValidationError("Este nome de usuário já está em uso.")

        return username
 
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()

        if not email or email == self.user.email:
            return self.user.email

        if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("Este e-mail já está em uso.")

        return email
 
    def clean(self):
        cleaned = super().clean()
        current = cleaned.get("current_password")
        new_p   = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
 
        if current or new_p or confirm:
            if not new_p:
                self.add_error("password", "Informe a nova senha.")
            if new_p and new_p != confirm:
                self.add_error("confirm_password", "As senhas não coincidem.")
            if not current or not self.user.check_password(current):
                self.add_error("current_password", "Senha atual incorreta.")
            if new_p:
                try:
                    validate_password(new_p, self.user)
                except ValidationError as e:
                    self.add_error("password", e)
 
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
 
    def save(self, commit=True):
        user = self.user
        data = self.cleaned_data
 
        user.first_name = data.get("first_name") or user.first_name
        user.last_name  = data.get("last_name")  or user.last_name
        user.username   = data.get("username")   or user.username
        user.email      = data.get("email")      or user.email
        user.bio        = data.get("bio", "")
 
        if data.get("password"):
            user.set_password(data["password"])
 
        if commit:
            user.save()
        return user

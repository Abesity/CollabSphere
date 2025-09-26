from django import forms
import re

class LoginForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'id': 'email', 'name': 'email'})
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'id': 'password', 'name': 'password'})
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(pattern, email):
            raise forms.ValidationError("Enter a valid email address.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not password:
            raise forms.ValidationError("Password is required.")
        return password


class RegistrationForm(forms.Form):
    username = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(required=True, widget=forms.PasswordInput)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        # Basic username rule: 3–30 chars, letters/numbers/underscore/dot/hyphen
        if not re.match(r"^[A-Za-z0-9._-]{3,30}$", username):
            raise forms.ValidationError("Username must be 3–30 characters (letters, numbers, ., _, -).")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        # Simple email regex: name@domain.tld
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            raise forms.ValidationError("Enter a valid email address.")
        return email

    def clean_password(self):
        pwd = self.cleaned_data.get("password") or ""
        # Keep it simple for sign-up; feel free to add min length later
        if not pwd:
            raise forms.ValidationError("Password is required.")
        return pwd
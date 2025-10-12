from django import forms
import re

class ProfileForm(forms.Form):
    full_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'id': 'full_name',
            'placeholder': 'Full Name',
        })
    )

    username = forms.CharField(
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={
            'id': 'username',
            'placeholder': 'Username',
        })
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'id': 'email',
            'placeholder': 'Email Address',
        })
    )

    title = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'id': 'title',
            'placeholder': 'Title',
        })
    )

    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'id': 'profile_picture',
        })
    )

    def clean_full_name(self):
        name = (self.cleaned_data.get("full_name") or "").strip()
        if name and not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s.'-]{2,100}$", name):
            raise forms.ValidationError(
                "Full name must contain only letters, spaces, apostrophes, or hyphens."
            )
        return name

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if username and not re.match(r"^[A-Za-z0-9._-]{3,30}$", username):
            raise forms.ValidationError(
                "Username must be 3–30 characters (letters, numbers, ., _, or -)."
            )
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            return email  # allow blank

        # Split into local and domain parts
        try:
            local_part, domain_part = email.rsplit("@", 1)
        except ValueError:
            raise forms.ValidationError("Enter a valid email address (e.g., name@example.com).")

        # Validate local part
        if not re.match(r"^[A-Za-z0-9._%+-]+$", local_part):
            raise forms.ValidationError("Invalid characters in email username.")

        # Stricter domain: main domain letters only, TLD letters only
        domain_regex = r"^[A-Za-z]+(\.[A-Za-z]+)+$"
        if not re.match(domain_regex, domain_part):
            raise forms.ValidationError(
                "Enter a valid email domain with letters only (e.g., example.com)."
            )

        # Block disposable emails
        disposable_domains = ("tempmail", "10minutemail", "guerrillamail", "mailinator", "yopmail")
        if any(domain in domain_part.lower() for domain in disposable_domains):
            raise forms.ValidationError("Disposable email addresses are not allowed.")

        return email




    def clean_profile_picture(self):
        pic = self.cleaned_data.get("profile_picture")

        if pic:
            if pic.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Profile picture must be under 5MB.")

            allowed_types = ["image/jpeg", "image/png", "image/webp"]
            if pic.content_type.lower() not in allowed_types:
                raise forms.ValidationError("Only JPEG, PNG, or WebP images are allowed.")
        return pic

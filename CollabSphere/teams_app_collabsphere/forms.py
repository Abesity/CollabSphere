# forms.py
from django import forms
from django.core.validators import FileExtensionValidator
from .models import Team

class CreateTeamForm(forms.Form):
    """Form for creating a new team"""
    
    team_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter team name...',
            'class': 'form-control'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Briefly describe your team...',
            'rows': 3,
            'class': 'form-control'
        })
    )
    
    icon_url = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        widget=forms.FileInput(attrs={
            'accept': 'image/*',
            'class': 'form-control-file'
        })
    )
    
    selected_members = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={
            'id': 'selectedMembersInput'
        })
    )

    def clean_team_name(self):
        """Validate team name"""
        team_name = self.cleaned_data.get('team_name', '').strip()
        if not team_name:
            raise forms.ValidationError('Team name is required')
        if len(team_name) < 2:
            raise forms.ValidationError('Team name must be at least 2 characters long')
        return team_name

    def clean_selected_members(self):
        """Validate and parse selected members"""
        selected_members = self.cleaned_data.get('selected_members', '')
        if selected_members:
            try:
                member_ids = [int(id.strip()) for id in selected_members.split(',') if id.strip()]
                return member_ids
            except ValueError:
                raise forms.ValidationError('Invalid member IDs format')
        return []

    def save(self, django_user):
        """Save the team using the Team model"""
        if not self.is_valid():
            raise ValueError("Cannot save invalid form")
        
        team_name = self.cleaned_data['team_name']
        description = self.cleaned_data['description']
        icon_file = self.files.get('icon_url')
        selected_members = self.cleaned_data['selected_members']
        
        # The selected_members are now Supabase user IDs, so we can pass them directly
        member_ids_string = ','.join(map(str, selected_members)) if selected_members else ''
        
        # Use the Team model to create the team
        result = Team.create_new_team(
            team_name=team_name,
            description=description,
            icon_file=icon_file,
            django_user=django_user,
            selected_members=member_ids_string
        )
        
        return result
            
    # EDIT TEAM
class EditTeamForm(forms.Form):
    """Form for editing an existing team"""
    
    team_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
    )
    icon_url = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        widget=forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control-file'})
    )
    remove_icon = forms.BooleanField(required=False)

    team_members = forms.CharField(required=False, widget=forms.HiddenInput())
    members_to_remove = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_team_name(self):
        team_name = self.cleaned_data.get('team_name', '').strip()
        if not team_name:
            raise forms.ValidationError('Team name is required')
        if len(team_name) < 2:
            raise forms.ValidationError('Team name must be at least 2 characters long')
        return team_name

    def clean_team_members(self):
        selected_members = self.cleaned_data.get('team_members', '')
        if selected_members:
            try:
                return [int(id.strip()) for id in selected_members.split(',') if id.strip()]
            except ValueError:
                raise forms.ValidationError('Invalid member IDs format')
        return []

    def clean_members_to_remove(self):
        members_to_remove = self.cleaned_data.get('members_to_remove', '')
        if members_to_remove:
            try:
                return [int(id.strip()) for id in members_to_remove.split(',') if id.strip()]
            except ValueError:
                raise forms.ValidationError('Invalid member IDs format for removal')
        return []
    def save(self, django_user, team_ID):
        """Update existing team in Supabase"""
        from .models import Team  # lazy import to avoid circular imports

        try:
            if not self.is_valid():
                raise ValueError("Cannot save invalid form")

            team_name = self.cleaned_data['team_name']
            description = self.cleaned_data['description']
            icon_file = self.files.get('icon_url')
            remove_icon = self.cleaned_data.get('remove_icon', False)
            team_members = self.cleaned_data['team_members']
            members_to_remove = self.cleaned_data['members_to_remove']

            # Use the Team model's update_team method with correct parameter name
            result = Team.update_team(
                team_ID=team_ID,  # FIXED: Use correct parameter name
                team_name=team_name,
                description=description,
                icon_file=icon_file,
                remove_icon=remove_icon,
                team_members=team_members,
                members_to_remove=members_to_remove,
                django_user=django_user
            )
            
            return result

        except Exception as e:
            print(f"Error updating team: {e}")
            return {'success': False, 'error': str(e)}
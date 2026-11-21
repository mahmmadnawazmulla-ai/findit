from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Category, Claim, FoundItem, LostItem, Profile


class BootstrapMixin:
    """Adds Bootstrap classes to every widget."""

    def _style(self):
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "form-check-input"
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs["class"] = "form-select"
            elif isinstance(w, forms.ClearableFileInput):
                w.attrs["class"] = "form-control"
            else:
                w.attrs["class"] = "form-control"


class RegisterForm(BootstrapMixin, UserCreationForm):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=15, required=False)

    class Meta:
        model = User
        fields = ("username", "email", "phone_number", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            Profile.objects.update_or_create(user=user, defaults={"phone_number": self.cleaned_data["phone_number"]})
        return user


class ProfileForm(BootstrapMixin, forms.ModelForm):
    phone_number = forms.CharField(max_length=15, required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].initial = getattr(getattr(self.instance, "profile", None), "phone_number", "")
        self._style()

    def save(self, commit=True):
        user = super().save(commit)
        Profile.objects.update_or_create(user=user, defaults={"phone_number": self.cleaned_data["phone_number"]})
        return user


class ItemFormMixin(BootstrapMixin):
    def _prepare(self):
        self._style()
        self.fields["category"].queryset = Category.objects.all()
        self.fields["category"].empty_label = "Choose a category"
        self.fields["date"].widget = forms.DateInput(attrs={"type": "date", "max": date.today().isoformat(), "class": "form-control"})
        self.fields["description"].widget.attrs["rows"] = 3

    def clean_date(self):
        d = self.cleaned_data["date"]
        if d > date.today():
            raise forms.ValidationError("The date cannot be in the future.")
        return d

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if img and hasattr(img, "size") and img.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Image must be smaller than 5 MB.")
        return img


class LostItemForm(ItemFormMixin, forms.ModelForm):
    class Meta:
        model = LostItem
        fields = ["item_name", "category", "colour", "description", "location", "date", "image", "hide_contact"]
        labels = {"location": "Where did you lose it?", "date": "When did you lose it?"}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._prepare()


class FoundItemForm(ItemFormMixin, forms.ModelForm):
    class Meta:
        model = FoundItem
        fields = ["item_name", "category", "colour", "description", "location", "date", "image",
                  "verification_question", "verification_answer", "hide_contact"]
        labels = {"location": "Where did you find it?", "date": "When did you find it?"}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._prepare()


class ClaimForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Claim
        fields = ["lost_item", "claim_description", "verification_response"]

    def __init__(self, *args, user=None, found_item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
        self.fields["lost_item"].queryset = LostItem.objects.filter(user=user, approval="approved").exclude(status="recovered")
        self.fields["lost_item"].empty_label = "I did not report it as lost"
        self.fields["lost_item"].required = False
        self.fields["claim_description"].widget.attrs["rows"] = 4
        if found_item and found_item.verification_question:
            self.fields["verification_response"].label = found_item.verification_question
            self.fields["verification_response"].required = True
        else:
            del self.fields["verification_response"]


class CategoryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._style()

from django.conf import settings
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class ItemBase(models.Model):
    """Fields shared by lost and found reports."""

    STATUS_OPEN, STATUS_MATCHED, STATUS_CLAIMED, STATUS_RECOVERED = "open", "matched", "claimed", "recovered"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_MATCHED, "Matched"),
        (STATUS_CLAIMED, "Claimed"),
        (STATUS_RECOVERED, "Recovered"),
    ]
    APPROVAL_CHOICES = [("pending", "Pending review"), ("approved", "Approved"), ("rejected", "Rejected")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)s_set")
    item_name = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    description = models.TextField(help_text="Brand, size, marks, anything that identifies the item.")
    colour = models.CharField(max_length=40)
    location = models.CharField(max_length=160)
    date = models.DateField()
    image = models.ImageField(upload_to="items/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    approval = models.CharField(max_length=10, choices=APPROVAL_CHOICES, default="approved")
    hide_contact = models.BooleanField(
        "Keep my contact details private", default=False,
        help_text="Others will not see your phone/email. Updates reach you through notifications.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.item_name} ({self.kind})"

    @property
    def status_badge(self):
        return {"open": "secondary", "matched": "warning", "claimed": "info", "recovered": "success"}[self.status]

    def get_absolute_url(self):
        return reverse("item_detail", args=[self.kind, self.pk])


class LostItem(ItemBase):
    kind = "lost"

    class Meta(ItemBase.Meta):
        verbose_name = "lost item"


class FoundItem(ItemBase):
    kind = "found"
    verification_question = models.CharField(
        max_length=200, blank=True,
        help_text="A question only the real owner can answer, e.g. 'What is the wallpaper on the phone?'",
    )
    verification_answer = models.CharField(
        max_length=200, blank=True, help_text="The correct answer. Only the admin can see this.",
    )

    class Meta(ItemBase.Meta):
        verbose_name = "found item"


class Match(models.Model):
    lost_item = models.ForeignKey(LostItem, on_delete=models.CASCADE, related_name="matches")
    found_item = models.ForeignKey(FoundItem, on_delete=models.CASCADE, related_name="matches")
    score = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("lost_item", "found_item")
        ordering = ["-score"]
        verbose_name_plural = "matches"

    def __str__(self):
        return f"{self.lost_item.item_name} <-> {self.found_item.item_name} ({self.score}%)"


class Claim(models.Model):
    STATUS_CHOICES = [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="claims")
    found_item = models.ForeignKey(FoundItem, on_delete=models.CASCADE, related_name="claims")
    lost_item = models.ForeignKey(
        LostItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="claims",
        verbose_name="My lost report (optional)",
    )
    claim_description = models.TextField("Why is this yours?", help_text="Describe marks, contents or proof of ownership.")
    verification_response = models.CharField("Answer to the verification question", max_length=200, blank=True)
    claim_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    admin_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "found_item")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Claim by {self.user} on {self.found_item.item_name}"

    @property
    def status_badge(self):
        return {"pending": "warning", "approved": "success", "rejected": "danger"}[self.claim_status]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message

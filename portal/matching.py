"""Smart matching: compares lost and found reports and suggests likely pairs.

Score (0-100) = name 30 + category 20 + colour 20 + location 20 + date 10.
Text similarity uses difflib (standard library) plus word overlap, so
"Black leather wallet" still matches "wallet".
"""
import re
from difflib import SequenceMatcher

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .models import FoundItem, LostItem, Match, Notification

WEIGHTS = {"name": 30, "category": 20, "colour": 20, "location": 20, "date": 10}


def _words(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def text_similarity(a, b):
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    wa, wb = _words(a), _words(b)
    overlap = len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0
    return max(ratio, overlap)


def date_score(lost, found):
    gap = abs((found.date - lost.date).days)
    if gap == 0:
        return 1.0
    if gap <= 2:
        return 0.7
    if gap <= 7:
        return 0.4
    return 0.0


def match_score(lost, found):
    s = WEIGHTS["name"] * text_similarity(lost.item_name, found.item_name)
    s += WEIGHTS["category"] * (1 if lost.category_id == found.category_id else 0)
    s += WEIGHTS["colour"] * text_similarity(lost.colour, found.colour)
    s += WEIGHTS["location"] * text_similarity(lost.location, found.location)
    s += WEIGHTS["date"] * date_score(lost, found)
    return round(s)


def notify(user, message, link=""):
    Notification.objects.create(user=user, message=message, link=link)
    if user.email:
        send_mail("FindIt update", f"{message}\n\nOpen FindIt to see the details.", None, [user.email], fail_silently=True)


def find_matches(item):
    """Run matching for a newly approved item and notify both owners."""
    if item.approval != "approved" or item.status in ("claimed", "recovered"):
        return []
    live = ("open", "matched")
    if isinstance(item, LostItem):
        candidates = FoundItem.objects.filter(approval="approved", status__in=live).exclude(user=item.user)
    else:
        candidates = LostItem.objects.filter(approval="approved", status__in=live).exclude(user=item.user)

    created = []
    for other in candidates:
        lost, found = (item, other) if isinstance(item, LostItem) else (other, item)
        score = match_score(lost, found)
        if score < settings.FINDIT_MATCH_THRESHOLD:
            continue
        match, is_new = Match.objects.get_or_create(lost_item=lost, found_item=found, defaults={"score": score})
        if not is_new:
            continue
        created.append(match)
        for obj in (lost, found):
            if obj.status == "open":
                obj.status = "matched"
                obj.save(update_fields=["status"])
        notify(lost.user, f"Possible match ({score}%) for your lost '{lost.item_name}'. Check the found report.",
               reverse("item_detail", args=["found", found.pk]))
        notify(found.user, f"Your found '{found.item_name}' may belong to someone ({score}% match).",
               reverse("item_detail", args=["lost", lost.pk]))
    return created

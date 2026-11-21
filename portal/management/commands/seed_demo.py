from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from portal.matching import find_matches
from portal.models import Category, FoundItem, LostItem, Profile


class Command(BaseCommand):
    help = "Creates demo users, items and an admin account (admin / admin12345)."

    def handle(self, *args, **opts):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@findit.local", "admin12345")
        cats = {c.name: c for c in Category.objects.all()}
        users = {}
        for name, phone in [("riya", "9800000001"), ("arjun", "9800000002"), ("sana", "9800000003")]:
            u, made = User.objects.get_or_create(username=name, defaults={"email": f"{name}@example.com"})
            if made:
                u.set_password("demo12345")
                u.save()
            Profile.objects.update_or_create(user=u, defaults={"phone_number": phone})
            users[name] = u
        if LostItem.objects.exists() or FoundItem.objects.exists():
            self.stdout.write("Demo items already exist - skipping.")
            return
        today = date.today()
        lost = [
            ("riya", "Black wallet", "Accessories", "Black", "College Campus - Library", today - timedelta(days=2),
             "Leather wallet with a student ID and two cards."),
            ("arjun", "College ID card", "Documents", "White", "Canteen", today - timedelta(days=1),
             "ID card of 2nd year Computer Science."),
            ("sana", "iPhone 13", "Electronics", "Blue", "Bus Stop - Main Gate", today - timedelta(days=3),
             "Blue cover, cracked screen guard."),
        ]
        found = [
            ("arjun", "Wallet", "Accessories", "Black", "College Campus - Library", today - timedelta(days=2),
             "Found near the reading hall.", "What card is at the front of the wallet?", "Library card"),
            ("riya", "Keys with keychain", "Keys", "Silver", "Parking Lot", today, "Three keys and a red tag.", "", ""),
        ]
        for u, n, c, col, loc, d, desc in lost:
            item = LostItem.objects.create(user=users[u], item_name=n, category=cats[c], colour=col, location=loc, date=d, description=desc)
            find_matches(item)
        for u, n, c, col, loc, d, desc, q, a in found:
            item = FoundItem.objects.create(user=users[u], item_name=n, category=cats[c], colour=col, location=loc, date=d,
                                            description=desc, verification_question=q, verification_answer=a)
            find_matches(item)
        self.stdout.write(self.style.SUCCESS("Demo data created. Admin: admin / admin12345, users: riya, arjun, sana / demo12345"))

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .matching import find_matches, match_score
from .models import Category, Claim, FoundItem, LostItem, Match


class FindItTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.get(name="Accessories")
        self.a = User.objects.create_user("a", "a@x.com", "pw12345!")
        self.b = User.objects.create_user("b", "b@x.com", "pw12345!")
        self.admin = User.objects.create_superuser("root", "r@x.com", "pw12345!")
        today = date.today()
        self.lost = LostItem.objects.create(user=self.a, item_name="Black wallet", category=self.cat, colour="Black",
                                            location="College Campus", date=today, description="d")
        self.found = FoundItem.objects.create(user=self.b, item_name="Wallet", category=self.cat, colour="black",
                                              location="College campus", date=today, description="d",
                                              verification_question="Which card?", verification_answer="Library")

    def test_matching_scores_and_notifies(self):
        self.assertGreaterEqual(match_score(self.lost, self.found), 90)
        find_matches(self.found)
        self.assertEqual(Match.objects.count(), 1)
        self.lost.refresh_from_db()
        self.assertEqual(self.lost.status, "matched")
        self.assertEqual(self.a.notifications.count(), 1)
        self.assertEqual(self.b.notifications.count(), 1)

    def test_no_match_for_different_item(self):
        other = FoundItem.objects.create(user=self.b, item_name="Umbrella", category=Category.objects.get(name="Other"),
                                         colour="Red", location="Bus stop", date=date(2020, 1, 1), description="d")
        self.assertLess(match_score(self.lost, other), 60)

    def test_public_pages_load(self):
        for name in ("home", "browse", "login", "register"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("item_detail", args=["found", self.found.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("qr_code", args=["lost", self.lost.pk])).status_code, 200)

    def test_login_required_and_staff_only(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
        self.client.login(username="a", password="pw12345!")
        self.assertEqual(self.client.get(reverse("manage_dashboard")).status_code, 302)

    def test_report_and_full_claim_flow(self):
        self.client.login(username="a", password="pw12345!")
        r = self.client.post(reverse("report_lost"), {
            "item_name": "Phone", "category": self.cat.pk, "colour": "Blue", "description": "x",
            "location": "Library", "date": date.today().isoformat()})
        self.assertEqual(r.status_code, 302)
        find_matches(self.found)
        # claim
        r = self.client.post(reverse("claim_create", args=[self.found.pk]), {
            "claim_description": "Mine, has my ID", "verification_response": "Library", "lost_item": self.lost.pk})
        self.assertEqual(r.status_code, 302)
        claim = Claim.objects.get()
        # owner cannot see finder contact before approval
        page = self.client.get(reverse("item_detail", args=["found", self.found.pk]))
        self.assertNotContains(page, "b@x.com")
        # admin approves
        self.client.login(username="root", password="pw12345!")
        self.assertEqual(self.client.get(reverse("manage_dashboard")).status_code, 200)
        for name in ("manage_reports", "manage_claims", "manage_users", "manage_categories", "manage_recovered"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.client.post(reverse("manage_claim_detail", args=[claim.pk]), {"decision": "approve"})
        claim.refresh_from_db(); self.found.refresh_from_db(); self.lost.refresh_from_db()
        self.assertEqual((claim.claim_status, self.found.status, self.lost.status), ("approved", "claimed", "claimed"))
        # claimant now sees contact
        self.client.login(username="a", password="pw12345!")
        self.assertContains(self.client.get(reverse("item_detail", args=["found", self.found.pk])), "b@x.com")
        self.assertEqual(self.client.get(reverse("notifications")).status_code, 200)
        # recover
        self.client.login(username="root", password="pw12345!")
        self.client.post(reverse("manage_claim_detail", args=[claim.pk]), {"decision": "recovered"})
        self.found.refresh_from_db()
        self.assertEqual(self.found.status, "recovered")

    def test_owner_cannot_claim_own_item(self):
        self.client.login(username="b", password="pw12345!")
        self.client.post(reverse("claim_create", args=[self.found.pk]), {"claim_description": "x", "verification_response": "y"})
        self.assertEqual(Claim.objects.count(), 0)

    def test_pending_report_hidden_from_public(self):
        self.lost.approval = "pending"; self.lost.save()
        self.assertEqual(self.client.get(reverse("item_detail", args=["lost", self.lost.pk])).status_code, 404)
        self.client.login(username="root", password="pw12345!")
        self.client.post(reverse("manage_report_action", args=["lost", self.lost.pk, "approve"]))
        self.lost.refresh_from_db()
        self.assertEqual(self.lost.approval, "approved")

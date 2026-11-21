import io
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CategoryForm, ClaimForm, FoundItemForm, LostItemForm, ProfileForm, RegisterForm
from .matching import find_matches, notify
from .models import Category, Claim, FoundItem, LostItem, Match

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="login")

MODELS = {"lost": LostItem, "found": FoundItem}


def get_item_or_404(kind, pk):
    model = MODELS.get(kind)
    if model is None:
        raise Http404("Unknown item type")
    return get_object_or_404(model.objects.select_related("category", "user"), pk=pk)


def can_see(user, item):
    return item.approval == "approved" or user.is_staff or (user.is_authenticated and item.user_id == user.id)


# ---------------------------------------------------------------- public pages
def home(request):
    live = {"approval": "approved"}
    stats = {
        "lost": LostItem.objects.filter(**live).count(),
        "found": FoundItem.objects.filter(**live).count(),
        "recovered": LostItem.objects.filter(status="recovered", **live).count()
        + FoundItem.objects.filter(status="recovered", **live).count(),
    }
    return render(request, "portal/home.html", {
        "latest_lost": LostItem.objects.filter(**live).select_related("category")[:4],
        "latest_found": FoundItem.objects.filter(**live).select_related("category")[:4],
        "categories": Category.objects.all(),
        "stats": stats,
    })


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to FindIt! Your account is ready.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("profile")
    return render(request, "portal/profile.html", {"form": form})


@login_required
def dashboard(request):
    u = request.user
    lost, found = LostItem.objects.filter(user=u), FoundItem.objects.filter(user=u)
    claims = Claim.objects.filter(user=u)
    # Claims other people made on items I found
    incoming = Claim.objects.filter(found_item__user=u).select_related("found_item", "user")[:5]
    matches = Match.objects.filter(Q(lost_item__user=u) | Q(found_item__user=u)).select_related("lost_item", "found_item")[:5]
    return render(request, "portal/dashboard.html", {
        "counts": {
            "lost": lost.count(), "found": found.count(), "claims": claims.count(),
            "recovered": lost.filter(status="recovered").count() + found.filter(status="recovered").count(),
        },
        "matches": matches,
        "incoming": incoming,
        "notes": u.notifications.all()[:5],
    })


# ------------------------------------------------------------------- reporting
@login_required
def report_item(request, kind):
    Form = LostItemForm if kind == "lost" else FoundItemForm
    form = Form(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.user = request.user
        item.approval = "approved" if settings.FINDIT_AUTO_APPROVE else "pending"
        item.save()
        found = find_matches(item)
        if item.approval == "pending":
            messages.info(request, "Report submitted. It will appear once an admin approves it.")
        elif found:
            messages.success(request, f"Report saved. We found {len(found)} possible match(es)!")
        else:
            messages.success(request, "Report saved. We'll notify you if a match appears.")
        return redirect(item)
    return render(request, "portal/report_form.html", {"form": form, "kind": kind})


def browse(request):
    g = request.GET
    kind = g.get("type", "all")
    q, cat, colour = g.get("q", "").strip(), g.get("category", ""), g.get("colour", "").strip()
    loc, d_from, d_to, status = g.get("location", "").strip(), g.get("from", ""), g.get("to", ""), g.get("status", "")

    def apply(qs):
        qs = qs.filter(approval="approved").select_related("category")
        if q:
            qs = qs.filter(Q(item_name__icontains=q) | Q(description__icontains=q))
        if cat.isdigit():
            qs = qs.filter(category_id=int(cat))
        if colour:
            qs = qs.filter(colour__icontains=colour)
        if loc:
            qs = qs.filter(location__icontains=loc)
        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)
        if status:
            qs = qs.filter(status=status)
        return qs

    items = []
    try:
        if kind in ("all", "lost"):
            items += list(apply(LostItem.objects.all()))
        if kind in ("all", "found"):
            items += list(apply(FoundItem.objects.all()))
    except Exception:  # bad date typed in the URL
        items = []
    items.sort(key=lambda i: i.created_at, reverse=True)
    page = Paginator(items, 9).get_page(g.get("page"))
    params = g.copy()
    params.pop("page", None)
    return render(request, "portal/browse.html", {
        "page": page, "categories": Category.objects.all(), "total": len(items),
        "querystring": params.urlencode(), "f": g, "status_choices": LostItem.STATUS_CHOICES,
    })


def item_detail(request, kind, pk):
    item = get_item_or_404(kind, pk)
    if not can_see(request.user, item):
        raise Http404
    user = request.user
    is_owner = user.is_authenticated and item.user_id == user.id
    ctx = {"item": item, "kind": kind, "is_owner": is_owner}

    if kind == "lost":
        ctx["matches"] = item.matches.select_related("found_item") if (is_owner or user.is_staff) else []
        ctx["show_contact"] = user.is_authenticated and not item.hide_contact
    else:
        ctx["matches"] = item.matches.select_related("lost_item") if (is_owner or user.is_staff) else []
        my_claim = item.claims.filter(user=user).first() if user.is_authenticated else None
        ctx["my_claim"] = my_claim
        ctx["can_claim"] = (user.is_authenticated and not is_owner and my_claim is None
                            and item.status in ("open", "matched"))
        ctx["show_contact"] = (is_owner or user.is_staff or (my_claim and my_claim.claim_status == "approved")) and not (
            item.hide_contact and not (is_owner or user.is_staff))
    return render(request, "portal/item_detail.html", ctx)


@login_required
@require_POST
def delete_item(request, kind, pk):
    item = get_item_or_404(kind, pk)
    if item.user_id != request.user.id and not request.user.is_staff:
        raise Http404
    item.delete()
    messages.success(request, "Report deleted.")
    return redirect("manage_reports" if request.user.is_staff and item.user_id != request.user.id else "my_reports")


@login_required
@require_POST
def mark_recovered(request, kind, pk):
    item = get_item_or_404(kind, pk)
    if item.user_id != request.user.id and not request.user.is_staff:
        raise Http404
    item.status = "recovered"
    item.save(update_fields=["status"])
    messages.success(request, "Marked as recovered. Great news!")
    return redirect(item)


def qr_code(request, kind, pk):
    """SVG QR code that links to the item page (print it and stick it on the item)."""
    item = get_item_or_404(kind, pk)
    if not can_see(request.user, item):
        raise Http404
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        raise Http404("Install the 'qrcode' package to enable QR codes.")
    url = request.build_absolute_uri(item.get_absolute_url())
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    buf = io.BytesIO()
    img.save(buf)
    return HttpResponse(buf.getvalue(), content_type="image/svg+xml")


@login_required
def my_reports(request):
    return render(request, "portal/my_reports.html", {
        "lost": LostItem.objects.filter(user=request.user).select_related("category"),
        "found": FoundItem.objects.filter(user=request.user).select_related("category"),
    })


# ---------------------------------------------------------------------- claims
@login_required
def claim_create(request, pk):
    found = get_object_or_404(FoundItem, pk=pk, approval="approved")
    if found.user_id == request.user.id:
        messages.error(request, "You cannot claim an item you reported as found.")
        return redirect(found)
    if found.status not in ("open", "matched"):
        messages.error(request, "This item has already been claimed.")
        return redirect(found)
    if Claim.objects.filter(user=request.user, found_item=found).exists():
        messages.info(request, "You have already submitted a claim for this item.")
        return redirect("my_claims")
    form = ClaimForm(request.POST or None, user=request.user, found_item=found)
    if request.method == "POST" and form.is_valid():
        claim = form.save(commit=False)
        claim.user, claim.found_item = request.user, found
        claim.save()
        notify(found.user, f"Someone submitted an ownership claim for your found '{found.item_name}'. An admin will verify it.",
               found.get_absolute_url())
        for admin_user in User.objects.filter(is_staff=True):
            notify(admin_user, f"New claim from {request.user.username} on '{found.item_name}'.", f"/manage/claims/{claim.pk}/")
        messages.success(request, "Claim submitted. You will be notified once it is verified.")
        return redirect("my_claims")
    return render(request, "portal/claim_form.html", {"form": form, "item": found})


@login_required
def my_claims(request):
    claims = Claim.objects.filter(user=request.user).select_related("found_item", "lost_item")
    return render(request, "portal/my_claims.html", {"claims": claims})


@login_required
def notifications(request):
    notes = list(request.user.notifications.all()[:100])
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "portal/notifications.html", {"notes": notes})


# ---------------------------------------------------------------- admin module
@staff_required
def manage_dashboard(request):
    lost_n, found_n = LostItem.objects.count(), FoundItem.objects.count()
    recovered = LostItem.objects.filter(status="recovered").count() + FoundItem.objects.filter(status="recovered").count()
    total = lost_n + found_n
    by_cat = Category.objects.annotate(n=Count("lostitem", distinct=True) + Count("founditem", distinct=True)).order_by("-n")
    status_counts = {}
    for label_key, label in LostItem.STATUS_CHOICES:
        status_counts[label] = (LostItem.objects.filter(status=label_key).count()
                                + FoundItem.objects.filter(status=label_key).count())
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    per_day = {
        "labels": [d.strftime("%d %b") for d in days],
        "lost": [LostItem.objects.filter(created_at__date=d).count() for d in days],
        "found": [FoundItem.objects.filter(created_at__date=d).count() for d in days],
    }
    ctx = {
        "stats": {
            "users": User.objects.count(), "lost": lost_n, "found": found_n, "recovered": recovered,
            "pending_reports": LostItem.objects.filter(approval="pending").count() + FoundItem.objects.filter(approval="pending").count(),
            "pending_claims": Claim.objects.filter(claim_status="pending").count(),
            "matches": Match.objects.count(),
            "rate": round(recovered * 100 / total) if total else 0,
        },
        "chart": ({
            "cats": {"labels": [c.name for c in by_cat if c.n], "values": [c.n for c in by_cat if c.n]},
            "status": {"labels": list(status_counts), "values": list(status_counts.values())},
            "days": per_day,
        }),
        "recent_claims": Claim.objects.filter(claim_status="pending").select_related("found_item", "user")[:5],
    }
    return render(request, "manage/dashboard.html", ctx)


@staff_required
def manage_reports(request):
    kind, approval = request.GET.get("type", "all"), request.GET.get("approval", "")
    items = []
    for k, model in MODELS.items():
        if kind in ("all", k):
            qs = model.objects.select_related("category", "user")
            if approval:
                qs = qs.filter(approval=approval)
            items += list(qs)
    items.sort(key=lambda i: i.created_at, reverse=True)
    return render(request, "manage/reports.html", {"items": items, "kind": kind, "approval": approval})


@staff_required
@require_POST
def manage_report_action(request, kind, pk, action):
    item = get_item_or_404(kind, pk)
    if action == "approve":
        item.approval = "approved"
        item.save(update_fields=["approval"])
        notify(item.user, f"Your {kind} report '{item.item_name}' was approved and is now public.", item.get_absolute_url())
        find_matches(item)
        messages.success(request, "Report approved.")
    elif action == "reject":
        item.approval = "rejected"
        item.save(update_fields=["approval"])
        notify(item.user, f"Your {kind} report '{item.item_name}' was rejected by the admin.", "")
        messages.success(request, "Report rejected.")
    elif action == "remove":
        notify(item.user, f"Your {kind} report '{item.item_name}' was removed for breaking the posting rules.", "")
        item.delete()
        messages.success(request, "Report removed.")
    else:
        raise Http404
    return redirect(request.POST.get("next") or "manage_reports")


@staff_required
def manage_claims(request):
    status = request.GET.get("status", "pending")
    claims = Claim.objects.select_related("found_item", "user", "lost_item")
    if status in ("pending", "approved", "rejected"):
        claims = claims.filter(claim_status=status)
    return render(request, "manage/claims.html", {"claims": claims, "status": status})


@staff_required
def manage_claim_detail(request, pk):
    claim = get_object_or_404(Claim.objects.select_related("found_item", "user", "lost_item"), pk=pk)
    found = claim.found_item
    if request.method == "POST":
        decision, note = request.POST.get("decision"), request.POST.get("admin_note", "").strip()
        if decision == "approve" and found.status in ("open", "matched"):
            claim.claim_status, claim.admin_note = "approved", note
            claim.save()
            found.status = "claimed"
            found.save(update_fields=["status"])
            if claim.lost_item:
                claim.lost_item.status = "claimed"
                claim.lost_item.save(update_fields=["status"])
            contact = ""
            if not found.hide_contact:
                phone = getattr(getattr(found.user, "profile", None), "phone_number", "")
                contact = f" Contact the finder: {found.user.email or 'no email'} {phone}".rstrip()
            notify(claim.user, f"Your claim for '{found.item_name}' was approved.{contact}", found.get_absolute_url())
            notify(found.user, f"The claim on your found '{found.item_name}' was verified. Please hand it over.", found.get_absolute_url())
            messages.success(request, "Claim approved.")
        elif decision == "reject":
            claim.claim_status, claim.admin_note = "rejected", note
            claim.save()
            notify(claim.user, f"Your claim for '{found.item_name}' was rejected. {note}".strip(), "")
            messages.success(request, "Claim rejected.")
        elif decision == "recovered" and claim.claim_status == "approved":
            found.status = "recovered"
            found.save(update_fields=["status"])
            if claim.lost_item:
                claim.lost_item.status = "recovered"
                claim.lost_item.save(update_fields=["status"])
            notify(claim.user, f"'{found.item_name}' is marked as recovered. Glad you got it back!", "")
            notify(found.user, f"Thank you! '{found.item_name}' is marked as recovered.", "")
            messages.success(request, "Item marked as recovered.")
        else:
            messages.error(request, "That action is not possible for this claim.")
        return redirect("manage_claim_detail", pk=pk)
    return render(request, "manage/claim_detail.html", {"claim": claim, "found": found})


@staff_required
def manage_users(request):
    users = User.objects.annotate(
        lost_n=Count("lostitem_set", distinct=True), found_n=Count("founditem_set", distinct=True),
    ).order_by("-date_joined")
    return render(request, "manage/users.html", {"users": users})


@staff_required
def manage_categories(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST":
        if "delete" in request.POST:
            cat = get_object_or_404(Category, pk=request.POST["delete"])
            if LostItem.objects.filter(category=cat).exists() or FoundItem.objects.filter(category=cat).exists():
                messages.error(request, f"'{cat.name}' is used by existing reports and cannot be deleted.")
            else:
                cat.delete()
                messages.success(request, "Category deleted.")
            return redirect("manage_categories")
        if form.is_valid():
            form.save()
            messages.success(request, "Category added.")
            return redirect("manage_categories")
    cats = Category.objects.annotate(n=Count("lostitem", distinct=True) + Count("founditem", distinct=True))
    return render(request, "manage/categories.html", {"form": form, "cats": cats})


@staff_required
def manage_recovered(request):
    items = list(LostItem.objects.filter(status="recovered").select_related("category", "user"))
    items += list(FoundItem.objects.filter(status="recovered").select_related("category", "user"))
    items.sort(key=lambda i: i.created_at, reverse=True)
    return render(request, "manage/recovered.html", {"items": items})

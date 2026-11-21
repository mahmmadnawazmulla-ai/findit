# FindIt - Smart Lost & Found Management System

A Django web app where users report lost and found items, search the listings, get
smart match suggestions, and claim items with admin-verified proof of ownership.

## Run it (5 steps)

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo     # optional: demo users, items and an admin account
python manage.py runserver
```

Open http://127.0.0.1:8000/

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | admin    | admin12345 |
| Users | riya, arjun, sana | demo12345 |

(Skip `seed_demo` and run `python manage.py createsuperuser` if you want your own admin.)

Run the tests: `python manage.py test`

## What is built

**User module** - register/login, profile, report lost, report found (with photo), browse,
search by name/keyword, filter by category/colour/location/date/status, item details,
submit claims, My Reports, My Claims, notifications (unread badge in the navbar).

**Admin module** (`/manage/`, staff only) - dashboard with charts and recovery rate, approve/reject/remove
reports, verify claims (the correct answer is shown only to admins), view users, manage categories,
recovered items. The full Django admin is also available at `/django-admin/`.

**Smart matching** (`portal/matching.py`) - every new approved report is compared with the opposite type.
Score = name 30 + category 20 + colour 20 + location 20 + date 10, using `difflib` similarity.
Pairs scoring 60 or more are saved as a `Match`, both users get a notification and an email,
and statuses move to *Matched*.

**Extras from your plan** - image upload, QR code per item (`/item/<type>/<id>/qr.svg`), email notifications
(printed in the terminal in development), claim verification question, status tracking
(Lost/Found -> Matched -> Claimed -> Recovered), anonymous reporting (hide contact details), analytics.

## Flow to demo
1. Log in as `riya`, open the found "Wallet" (matched 100% with her lost "Black wallet").
2. Click **Claim this item**, answer the question ("Library card"), submit.
3. Log in as `admin`, open **Admin > Claims**, review and approve. The claimant now sees the finder's contact.
4. Mark as recovered. Check the dashboard statistics.

## Settings you can change (`config/settings.py`)
- `FINDIT_MATCH_THRESHOLD = 60` - how strict matching is.
- `FINDIT_AUTO_APPROVE = True` - set `False` so every report waits for admin approval.
- Email: switch to the SMTP block to send real emails.

## Project layout
```
config/            project settings and root urls
portal/models.py   Category, Profile, LostItem, FoundItem, Match, Claim, Notification
portal/matching.py smart matching engine
portal/views.py    user + admin views
portal/forms.py    forms
templates/         HTML (Bootstrap 5)
static/css/        custom styles (your colour palette)
```
Note: lost/found location and date fields are named `location` and `date` in both models so one set of code serves both.
Bootstrap, icons, fonts and Chart.js load from CDNs, so the browser needs internet access.

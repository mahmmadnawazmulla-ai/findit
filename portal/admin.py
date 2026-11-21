from django.contrib import admin

from .matching import find_matches
from .models import Category, Claim, FoundItem, LostItem, Match, Notification, Profile


class ItemAdmin(admin.ModelAdmin):
    list_display = ("item_name", "user", "category", "colour", "location", "date", "status", "approval")
    list_filter = ("approval", "status", "category")
    search_fields = ("item_name", "description", "location", "user__username")
    actions = ["approve", "reject"]

    @admin.action(description="Approve selected reports")
    def approve(self, request, queryset):
        for item in queryset:
            item.approval = "approved"
            item.save(update_fields=["approval"])
            find_matches(item)

    @admin.action(description="Reject selected reports")
    def reject(self, request, queryset):
        queryset.update(approval="rejected")


admin.site.register(LostItem, ItemAdmin)
admin.site.register(FoundItem, ItemAdmin)
admin.site.register(Category)
admin.site.register(Profile)
admin.site.register(Match)
admin.site.register(Notification)


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("found_item", "user", "claim_status", "created_at")
    list_filter = ("claim_status",)

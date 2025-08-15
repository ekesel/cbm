from django.contrib import admin
from .models import MappingVersion, ETLJobRun, BoardCredential
from .models import NotificationChannel

@admin.register(MappingVersion)
class MappingVersionAdmin(admin.ModelAdmin):
    list_display = ("version", "active", "created_at", "updated_at")
    list_filter = ("active",)
    search_fields = ("version", "description")

@admin.register(ETLJobRun)
class ETLJobRunAdmin(admin.ModelAdmin):
    list_display = ("job_name", "board", "status", "started_at", "finished_at", "records_pulled", "records_normalized", "records_failed")
    list_filter = ("status", "job_name", "board")
    search_fields = ("run_id", "job_name")
    readonly_fields = ("run_id", "started_at", "finished_at", "created_at")

@admin.register(BoardCredential)
class BoardCredentialAdmin(admin.ModelAdmin):
    list_display = ("board", "api_base_url", "auth_type", "updated_at")
    search_fields = ("board__name", "api_base_url")
    readonly_fields = ("created_at", "updated_at")

    # Mask token in admin form display
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj:
            form.base_fields["username"].initial = obj.username
        return form

    def save_model(self, request, obj, form, change):
        # Accept token via POST field named 'token_plain' (use admin raw_id or form override if you prefer)
        token_plain = request.POST.get("token_plain")
        if token_plain:
            obj.set_token(token_plain)
        super().save_model(request, obj, form, change)

@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "board", "channel_type", "is_active", "updated_at")
    list_filter = ("channel_type", "is_active")
    search_fields = ("name", "board__name")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        token_plain = request.POST.get("webhook_plain")
        if token_plain:
            obj.set_webhook(token_plain)
        super().save_model(request, obj, form, change)
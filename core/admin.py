from django.contrib import admin, messages

try:
	from allauth.socialaccount.models import SocialApp
except Exception:
	SocialApp = None


if SocialApp is not None:
	# Avoid registering if another app already registered SocialApp
	try:
		already = SocialApp in admin.site._registry
	except Exception:
		already = False

	if not already:
		@admin.register(SocialApp)
		class SocialAppAdmin(admin.ModelAdmin):
			list_display = ('provider', 'name')

			def save_model(self, request, obj, form, change):
				super().save_model(request, obj, form, change)
				# After saving, check for duplicates (same provider & overlapping sites)
				try:
					for site in obj.sites.all():
						duplicates = SocialApp.objects.filter(provider=obj.provider, sites=site).exclude(id=obj.id)
						if duplicates.exists():
							messages.warning(request, f"Multiple SocialApp entries exist for provider '{obj.provider}' and site '{site.domain}'. Consider running the dedupe management command.")
				except Exception:
					# Be conservative and silent on errors here
					pass
	else:
		# If already registered, optionally attach a post-save hook by listening to model signals
		pass


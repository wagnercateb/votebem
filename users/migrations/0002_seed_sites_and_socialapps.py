"""
Data migration to ensure proper django.contrib.sites entries exist for the
production domains and that any existing allauth SocialApp(s) are attached
to the correct Site(s) without duplication.

This migration focuses on:
1) Setting the default Site (id=1) to the canonical domain (e.g., votebem.online)
2) Ensuring a second Site exists for the www domain (e.g., www.votebem.online)
3) Attaching existing SocialApp(s) (Google, Facebook if present) to those Sites
   and de-duplicating attachments so each Site has at most one SocialApp per
   provider.

IMPORTANT NOTES:
- We intentionally avoid creating placeholder SocialApps without credentials.
  If a SocialApp does not yet exist for a given provider, we simply skip
  attaching and leave configuration to the admin or environment-driven setup.
- This migration is safe to run multiple times; it uses idempotent operations
  and deduplication, so re-running won't produce duplicate attachments.
- SITE_ID is best controlled via settings/environment. This migration updates
  the Site with id=1 to be your canonical domain so that the default
  SITE_ID=1 remains correct out-of-the-box. If you prefer a different Site
  as default, set `SITE_ID` via environment (`SITE_ID=<id>`) and ensure your
  settings read it accordingly.

Environment overrides:
- PRIMARY_SITE_DOMAIN: canonical domain (default: "votebem.online")
- WWW_SITE_DOMAIN: www domain (default: "www.votebem.online")

This migration includes extensive comments to ease maintenance and auditing.
"""

from django.db import migrations


def seed_sites_and_socialapps(apps, schema_editor):
    """
    Forward migration function that:
    - Updates Site(id=1) to canonical domain and name
    - Ensures a Site exists for the www domain
    - Attaches existing SocialApp(s) to Sites and deduplicates
    """
    import os

    # Access historical versions of models via apps.get_model to ensure
    # migration compatibility even if models evolve later.
    Site = apps.get_model('sites', 'Site')
    SocialApp = apps.get_model('socialaccount', 'SocialApp')

    # Resolve domains from environment or use safe defaults matching the
    # current production setup.
    canonical_domain = os.environ.get('PRIMARY_SITE_DOMAIN', 'votebem.online').strip()
    www_domain = os.environ.get('WWW_SITE_DOMAIN', f'www.{canonical_domain}').strip()

    # 1) Update default Site (id=1) to the canonical domain so SITE_ID=1 is correct.
    try:
        default_site = Site.objects.get(id=1)
        # Use a human-readable name derived from the domain.
        default_site.domain = canonical_domain
        default_site.name = canonical_domain
        default_site.save(update_fields=['domain', 'name'])
    except Site.DoesNotExist:
        # If id=1 doesn't exist (rare), create it explicitly as the canonical site.
        default_site = Site.objects.create(id=1, domain=canonical_domain, name=canonical_domain)

    # 2) Ensure www Site exists
    www_site, _created_www = Site.objects.get_or_create(
        domain=www_domain,
        defaults={'name': www_domain},
    )

    # Helper: choose a primary SocialApp for a provider.
    # We prefer the first one found (by id) with non-empty credentials; otherwise fall back to first.
    def choose_primary(provider: str):
        apps_qs = SocialApp.objects.filter(provider=provider).order_by('id')
        if not apps_qs.exists():
            return None
        # Prefer app with both client_id and secret present
        for app in apps_qs:
            cid = (app.client_id or '').strip()
            sec = (app.secret or '').strip()
            if cid and sec:
                return app
        # Fallback to the first
        return apps_qs.first()

    # Helper: attach primary SocialApp to a site and remove duplicates
    def attach_and_deduplicate(provider: str, site: Site):
        primary = choose_primary(provider)
        if primary is None:
            # No SocialApp for this provider exists yet; skip gracefully.
            return

        # If site is not attached to primary, attach it.
        if site.pk not in primary.sites.values_list('pk', flat=True):
            primary.sites.add(site)

        # Remove duplicate attachments: keep `primary` attached, detach others.
        duplicates = SocialApp.objects.filter(provider=provider, sites__pk=site.pk).exclude(pk=primary.pk)
        for dup in duplicates:
            dup.sites.remove(site)

    # 3) Attach SocialApps (Google and Facebook if present) to both sites and deduplicate
    for provider in ('google', 'facebook'):
        attach_and_deduplicate(provider, default_site)
        attach_and_deduplicate(provider, www_site)


def noop_reverse(apps, schema_editor):
    """
    Reverse migration intentionally left as a no-op:
    - We do not delete Sites or detach SocialApps on reverse to avoid
      breaking production configurations if a rollback occurs.
    """
    pass


class Migration(migrations.Migration):
    # This migration depends on the initial users app migration and the
    # contrib.sites / allauth tables being present.
    # If your project has explicit migrations for `sites` or `socialaccount`,
    # ensure those migrations run before this one.
    dependencies = [
        ('users', '0001_initial'),
        ('sites', '0002_alter_domain_unique'),  # Django's default sites migration sequencing
        ('socialaccount', '0001_initial'),      # allauth SocialApp initial migration
    ]

    operations = [
        migrations.RunPython(seed_sites_and_socialapps, noop_reverse),
    ]


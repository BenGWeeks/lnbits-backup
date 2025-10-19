# Troubleshooting

| Problem | Solution |
|---------|----------|
| MORE button not appearing on extension card | **Config.json requirements:** Must have `images` array with at least one image, `description_md` URL, and `terms_and_conditions_md` URL. Do NOT include `hidden`, `migration_module`, or `db_name` in config.json (those belong in manifest.json only). **Manifest.json requirements:** Must have `name`, `short_description`, `tile`, `contributors`, `hidden`, `min_lnbits_version`, `version`, plus `migration_module` and `db_name`. Do not use `featured` or `installed_release` structure. After making changes, hard refresh browser (Ctrl+Shift+F5) to clear cache. |

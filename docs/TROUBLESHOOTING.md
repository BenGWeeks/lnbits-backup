# Troubleshooting

| Problem | Solution |
|---------|----------|
| MORE button not appearing on extension card | The `manifest.json` file must have the correct structure with fields: `name`, `short_description`, `tile`, `contributors`, `hidden`, `min_lnbits_version`, and `version`. Do not use the `featured` or `installed_release` structure. Also ensure `config.json` has an `images` array (even if empty or with placeholder) and a `description_md` URL pointing to an accessible markdown file. |

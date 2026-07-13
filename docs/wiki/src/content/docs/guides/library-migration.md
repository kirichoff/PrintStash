---
title: Library migration
description: Move Models and Artifacts between PrintStash installations.
---

Open **Settings → Overview → Library migration** and select **Export full library**. PrintStash creates a `printstash-library-v1.zip` archive containing accessible Models, original Artifact blobs, extracted metadata, collections, tags, print history, favorites, and saved views.

On destination installation, sign in as administrator and choose **Import archive**. Import validates archive paths, sizes, and SHA-256 hashes before writing. Existing Models and Artifacts are deduplicated by their hashes, so importing same archive again is safe.

Archive intentionally excludes accounts, passwords, API keys, printer credentials, runtime configuration, trash, thumbnails, and backup archives. Keep normal backup procedure for disaster recovery; portable archive exists for library migration.

For files already stored on NAS, configure external library first. Targeted folder imports only accept paths below configured root and never expose arbitrary server filesystem paths.

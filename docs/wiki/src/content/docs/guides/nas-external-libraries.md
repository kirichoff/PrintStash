---
title: NAS folders (External Libraries)
description: Mirror a folder on your NAS in place — index files where they live instead of copying them into the vault.
---

Most of PrintStash works on the **vault**: you upload a file, PrintStash copies
the bytes into its own storage, and from then on it owns that copy. External
Libraries are the opposite arrangement. You point PrintStash at a folder you
already keep — typically a share on a NAS — and it indexes the files **where they
live**. Nothing is copied into the vault except the generated thumbnail and the
parsed metadata. The folder stays the source of truth, and you can still browse,
read, and write to it with your file manager, OctoPrint, or anything else.

This page explains how the mirroring works and, importantly, how to make the NAS
folder visible to PrintStash in the first place.

:::note
External Libraries are **opt-in and off by default**, and only a superuser can
manage them. Turn the feature on under **Settings → NAS folders** before any of
this is available.
:::

## How it works

### The folder is the source of truth

When you add a library you give PrintStash an absolute folder path. From then on,
a **scan** walks that folder and reconciles the index against what is actually on
disk:

- **New file on disk** → indexed in place. PrintStash hashes it, parses it,
  generates a thumbnail, and creates the model — but leaves the file exactly
  where it is. The model's file shows a **Linked** badge.
- **File removed from disk** → moved to trash in PrintStash. The bytes are
  already gone, so nothing is deleted on disk. If that was the model's last file,
  the model is trashed too.
- **File changed on disk** (size or modification time moved) → re-hashed. If the
  content really changed, the metadata and thumbnail are rebuilt; if only the
  timestamp moved, PrintStash just records the new signature.

Scans run automatically on the interval you set per library (default every 60
minutes), and you can also press **Scan now** at any time.

### Write-back keeps the folder complete

Mirroring is bidirectional. When you upload a file or add a revision through the
web UI and that model belongs to a library, PrintStash writes the new file
**into the NAS folder** rather than into the vault. Revisions automatically
follow their model's library; brand-new uploads let you pick the destination in
the upload modal.

Write-back is collision-safe: PrintStash only ever **adds** files to your folder.
It never overwrites or deletes bytes that are already there.

### Mirror vs. single collection

Each library chooses how on-disk subfolders map to PrintStash collections:

- **Mirror subfolders as collections** — the folder tree becomes your collection
  tree. `…/functional/brackets/x.stl` lands in the `functional/brackets`
  collection.
- **Single collection (flat)** — everything from the folder drops into one
  collection you choose.

### Safety: an unmounted NAS never causes deletions

This is the part that matters most for a NAS. If the share is unmounted, the
folder path can suddenly look *empty* even though your files are perfectly safe
on the NAS — and a naive "mirror" would read that as "every file was deleted"
and trash your whole library.

PrintStash refuses to do that. A scan **aborts without changing anything** when:

- the folder path is missing, not a directory, or unreadable, **or**
- the folder is empty while the library still has indexed files.

In either case the scan is marked as errored and your index is left untouched.
Once the share is mounted again, the next scan reconciles normally.

## Making the NAS folder visible to PrintStash

This is the step people miss. PrintStash runs **inside a Docker container**, and
a container can only see paths that have been mounted into it. The default
`docker-compose.yml` mounts named volumes for vault data, thumbnails, the
database, and backups — but it has **no idea** your NAS exists. The absolute path
you type into the library form is resolved *inside the `api` container*, not on
your host.

So there are two layers to set up:

1. Mount the NAS on the **host** (the machine running Docker).
2. Bind-mount that host path into the **`api` container**.

### Step 1 — Mount the NAS on the host

Mount your share with whatever your NAS speaks. A couple of common examples
(adjust addresses, share names, and credentials):

```bash
# NFS
sudo mkdir -p /mnt/nas/3d
sudo mount -t nfs 192.168.1.10:/volume1/3dprints /mnt/nas/3d

# SMB / CIFS
sudo mkdir -p /mnt/nas/3d
sudo mount -t cifs //192.168.1.10/3dprints /mnt/nas/3d \
  -o username=YOURUSER,uid=$(id -u),gid=$(id -g),iocharset=utf8
```

To make it survive reboots, add the mount to `/etc/fstab` instead of running
`mount` by hand. Confirm you can list files at `/mnt/nas/3d` before moving on —
if the host can't see them, the container never will.

### Step 2 — Bind-mount the host path into the container

Don't edit `docker-compose.yml` directly; add a **`docker-compose.override.yml`**
next to it (Compose merges it automatically). This keeps your local mounts
separate from the shipped file and survives upgrades:

```yaml
# docker-compose.override.yml
services:
  api:
    volumes:
      - /mnt/nas/3d:/mnt/nas/3d
```

Here the host path `/mnt/nas/3d` is exposed at the **same path inside the
container**. Using an identical path on both sides is the least confusing choice,
but you can map to a different container path if you prefer — just remember that
the path you enter in PrintStash must be the **container** side.

:::tip
If your NAS share is read-only or you want PrintStash to treat it as read-only
(no write-back), append `:ro` to the mount: `- /mnt/nas/3d:/mnt/nas/3d:ro`. Note
that web uploads/revisions for models in that library will then fail to write.
:::

Apply the change:

```bash
docker compose up -d
```

### Step 3 — Add the library in PrintStash

1. Go to **Settings → NAS folders** and toggle the feature on.
2. Click **Add a folder** and fill in:
   - **Name** — anything memorable, e.g. `NAS models`.
   - **Absolute folder path** — the **container** path, e.g. `/mnt/nas/3d`.
   - **Scan interval** — how often to auto-scan, in minutes.
   - **Collection mode** — mirror subfolders or a single flat collection.
3. Save. PrintStash validates that the path exists and is readable, then runs an
   initial scan. Use **Scan now** to re-sync on demand.

If saving fails with a path error, the container can't see the folder — recheck
Steps 1 and 2 (`docker compose exec api ls /mnt/nas/3d` is a quick way to confirm
the container sees your files).

## Good to know

- **Removing a library never deletes your files.** It moves the indexed models
  and files to trash inside PrintStash; the bytes on the NAS are left untouched.
- **Linked files are never garbage-collected.** PrintStash's trash hard-delete
  and storage GC skip external bytes entirely — only vault-owned copies are ever
  removed from disk.
- **Permissions matter.** The `api` container must be able to read (and, for
  write-back, write) the mounted path. With SMB/CIFS, set `uid`/`gid` at mount
  time so the container's user can access the files.
- **Big first scan?** The initial scan hashes and parses every supported file in
  the folder, so the first run on a large NAS can take a while. Subsequent scans
  only touch files whose size or modification time changed.

# Observed disposable Linux build evidence

`verification.json` records actual successful run41214056349 and the downloaded
artifact digest. `DEPENDENCIES.lock` and `OS-PACKAGES.lock` are observed inventories
inside that built application image. They are not a universal Linux wheel lock,
complete vulnerability clearance or bit-reproducible future source build.

The application image ID is local to the disposable runner. It was not published
to a registry or retained as a deployable image archive; the ID alone cannot be
pulled onto a VPS. Build, inspect and explicitly approve a trusted artifact before
promotion, then use its immutable registry digest or verified transferred image ID.
No registry publishing credentials, private keys, source photos or databases are
included here. D1/D2/CS1/CS2 remain approval-held; public release is not approved.

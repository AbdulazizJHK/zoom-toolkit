# Microsoft Store submission guide

This folder contains everything needed to package Zoom Toolkit as an MSIX for the
Microsoft Store.

```
msix/
  AppxManifest.xml     package manifest (edit Identity before submitting)
  Assets/              Store tile/logo PNGs
  build_msix.ps1       builds ZoomToolkit.msix from dist\Zoom Toolkit.exe
```

## Prerequisites
- Windows 10/11 **SDK** installed (provides `makeappx.exe` / `signtool.exe`).
- A built app: run `pyinstaller "Zoom Toolkit.spec" --noconfirm --clean` first.
- A **Partner Center** developer account (one-time ~$19 individual):
  https://partner.microsoft.com/dashboard

## Steps

1. **Reserve the app name** in Partner Center → Apps and games → New product →
   MSIX/PWA app. Reserve e.g. "Zoom Toolkit".

2. **Copy your identity values.** In Partner Center open
   *Product management → Product identity* and copy:
   - Package/Identity/**Name**
   - Package/Identity/**Publisher** (looks like `CN=ABCD1234-...`)
   - **Publisher display name**

3. **Edit `AppxManifest.xml`** — replace the three `Identity`/`PublisherDisplayName`
   placeholders with the values from step 2.

4. **Build the package (unsigned — the Store signs it):**
   ```powershell
   pwsh -File msix\build_msix.ps1
   ```
   Produces `msix\ZoomToolkit.msix`.

5. **(Optional) Test locally first** — build a self-signed copy and install it:
   ```powershell
   pwsh -File msix\build_msix.ps1 -Sign
   ```
   Follow the printed instructions to trust the test cert and `Add-AppxPackage`.
   **Verify Extract / Clean / Sort actually move files** inside the packaged app.
   If any file operation is blocked, add `broadFileSystemAccess` to the manifest
   (see the comment there) and rebuild.

6. **Create the submission** in Partner Center:
   - **Packages:** upload `ZoomToolkit.msix`.
   - **Store listing:** description, screenshots (reuse the app screenshots),
     category (e.g. *Productivity* or *Multimedia design*).
   - **Privacy policy URL:** point to the raw `PRIVACY.md`, e.g.
     `https://github.com/AbdulazizJHK/zoom-toolkit/blob/main/PRIVACY.md`
   - **Pricing:** Free. **Age rating:** complete the questionnaire.
   - Submit for certification (usually hours–days).

## Updating later
Bump `Version` in `AppxManifest.xml` (e.g. `2.1.0.0`), rebuild, and submit a new
package. Keep the four `Version` parts; the Store requires an increasing version.

## Note on signing & cost
- For the **Store**, you do **not** need a paid certificate — Microsoft signs the
  package on ingestion.
- A paid code-signing certificate (~$100+/yr) is only needed if you also want to
  distribute the MSIX **outside** the Store. The self-signed cert from
  `-Sign` is for local testing only and must never be shipped.

# Bitwarden True Portable Builder — ZIP-only, manual GitHub Actions

**Status:** Build kit prepared. 12 offline tests passed. The Windows GitHub Actions build and Bitwarden account / settings portability **have not yet been tested**. Unlike a ready-made Bitwarden application, this ZIP contains **builder files only**, not your password manager or vault.

## What this does

- Downloads **only** the official `Bitwarden-Portable-<version>.exe` from the published [Bitwarden Desktop release](https://github.com/bitwarden/clients/releases), not the installer or commercial edition.
- Confirms the downloaded file's SHA-256 against the official GitHub release asset digest (and also our pinned value for `2026.10.0`). Stops on any mismatch or unsupported release.
- Downloads the official Bitwarden Windows icon from the **same release tag** and uses it for the root launcher and PortableApps Menu icons.
- Compiles a tiny Windows launcher that sets Bitwarden's officially documented `BITWARDEN_APPDATA_DIR` to its own `Data/Bitwarden` directory. It also sets `TEMP` and `TMP` for the Bitwarden child process to `Data/Temp`, without changing global Windows settings.
- Creates one downloadable portable ZIP with the `App / Data / Other / BitwardenPortable.exe` structure.
- **Never downloads, reads, or includes private Bitwarden vault data in the GitHub Action.** The generated ZIP includes an empty `Data` folder with a reminder file only.

The launcher runs the official, unmodified Bitwarden portable executable. This is a *community ZIP package*, NOT an official Bitwarden edition or a `.paf.exe` installer.

## One-time setup with GitHub Desktop

1. In a web browser, open https://github.com/new and create a **new empty repository** called `Bitwarden-Portable-Builder`. Public is fine for these builder scripts. Keep *Add a README*, *.gitignore* and *license* unchecked so your repository is empty.
2. Download the **builder ZIP**, right-click it and choose **Extract All**. Open the extracted folder.
3. In GitHub Desktop, choose **File > Clone repository**, select the newly created repository and choose a location on your computer.
4. In GitHub Desktop, click **Repository > Show in Explorer**. Copy **all the extracted files and folders** to the repository folder: `.github`, `builder`, `tests`, `README.md`, `START-HERE.txt`, `.gitignore`. **Copy the contents, not the builder ZIP itself.** GitHub Desktop handles the `.github` folder so you don't need the GitHub website upload workaround.
5. Return to GitHub Desktop. Under **Changes**, enter `Add Bitwarden portable builder` in the Summary field. Click **Commit to main**, then **Push origin**.

**Security note:** NEVER copy your actual `BitwardenPortable/Data` folder into this repository. It contains encrypted vault data and account state. The provided `.gitignore` blocks common accidental paths, but it is not a substitute for keeping your actual vault data out of GitHub.

## Build the portable application (repeat when you need to update)

1. Open your `Bitwarden-Portable-Builder` repository on GitHub.com.
2. Go to **Actions** on the top menu. Choose **Build Bitwarden Portable ZIP (Manual)** on the left.
3. Click **Run workflow**, select `main`, and use **version = 2026.10.0** for your first build. Leave **expected_sha256** empty. Click the green Run workflow button.
4. Wait for the run to finish. If it ends with a **green check**, open that run, scroll to **Artifacts**, and download `Bitwarden-Portable-2026.10.0`.
5. Extract the GitHub Actions artifact ZIP. Inside is `Bitwarden-v2026.10.0-TruePortable.zip`. Extract that ZIP, too.
6. Open the resulting `BitwardenPortable` directory and **always launch `BitwardenPortable.exe` from the root** — not `App/Bitwarden/Bitwarden-Portable.exe` directly. The root launcher supplies the portable data location.
7. Sign in normally and confirm that settings appear in `BitwardenPortable/Data/Bitwarden`.

If GitHub shows a **red X**, open the failed step and download the Actions logs. The error may relate to a blocked download, an upstream asset change, or Windows compilation. Do not bypass SHA-256 verification.

## Expected output

```text
BitwardenPortable/
  BitwardenPortable.exe          <-- RUN THIS FILE
  App/
    Bitwarden/
      Bitwarden-Portable.exe    <-- official unmodified 2026.10.0 binary
    AppInfo/
      appinfo.ini
      appicon.ico
      appicon_16.png
      appicon_32.png
      appicon_75.png
      appicon_128.png
      appicon_256.png
  Data/                          <-- KEEP THROUGH ALL UPGRADES
    README-PRESERVE-DURING-UPDATE.txt
    Bitwarden/                  <-- populated on first launch
    Temp/                       <-- populated on first launch
  Other/Source/
    BUILD-INFO.txt
    SECURITY.txt
    OFFICIAL-LICENSE-URL.txt
```

### Update without losing account data

1. **Exit Bitwarden completely**, including any tray/background process.
2. **Back up the whole `Data` folder** somewhere secure. Encrypt backups containing Bitwarden data. Do not upload them to GitHub or public file-sharing services.
3. Enter the **new official stable version** in your builder's Actions page, and build again. Leave the optional checksum blank if the official GitHub API provides a digest. Otherwise, independently copy the published official release SHA-256 into that field; the workflow **will refuse to build without verification**.
4. Download and extract the new application ZIP to a **separate temporary folder**.
5. In your old `BitwardenPortable` folder, replace **only** `App` and `BitwardenPortable.exe` with those from the new package. Leave your existing `Data` folder as-is.
6. Launch `BitwardenPortable.exe` and confirm Bitwarden settings and vault synchronization. You may need to sign in again after a Windows reinstall or change in authentication state.

**Do not copy a new empty Data folder over your existing Data folder.** Bitwarden's online encrypted vault remains on Bitwarden's service or your self-hosted server, but the local Data folder contains important settings and cached account state.

### Security warnings specific to Bitwarden

- The **official Windows portable edition lacks Secure Storage and Process Isolation** compared with the normal installed Windows edition. This is documented by Bitwarden. Biometric unlock may be available but depends on Windows; avoid relying on cross-computer persistence.
- Portable Bitwarden data contains **encrypted vault cache and authentication/session state**. This is still sensitive, even when the vault itself is encrypted. Store it on an encrypted drive (e.g., BitLocker) and use a strong master password plus two-step login.
- Local Windows integration and **desktop-to-browser native messaging** may change user-level registry/browser settings outside the portable folder. Do not enable that integration if you need minimal host changes; verify first.
- The official portable executable is self-extracting and may generate significant temporary data in `Data/Temp`. The launcher does not delete it automatically because the Bitwarden process may still be using it. You may clean it manually only after Bitwarden has completely closed, and after safeguarding all app data.
- Portable mode does **not** mean zero Windows operating-system traces. Test `%APPDATA%`, `%LOCALAPPDATA%`, `%TEMP%`, system credentials and browser integration independently if that matters.
- No automatic build trigger, no automatic upstream sync, no PAF packaging.
- The Windows version of the portable Bitwarden release is distributed as a single portable EXE. The workflow currently builds **Windows x64**. Other architectures would require explicit review and testing.

## References

- [Official Bitwarden desktop releases](https://github.com/bitwarden/clients/releases)
- [Bitwarden documentation: local encrypted data paths and `BITWARDEN_APPDATA_DIR`](https://bitwarden.com/help/data-storage/)
- [Bitwarden documentation: installed vs portable Windows features](https://bitwarden.com/help/desktop-app-feature-support/)
- [Official Bitwarden clients repository](https://github.com/bitwarden/clients)
- [PortableApps.com Format 3.9 — layout, icons and menu metadata](https://portableapps.com/development/portableapps.com_format)

The community launcher is separate from Bitwarden. The official application binary is not altered. Respect the publisher's distribution terms and license when sharing this package.

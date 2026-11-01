# Contributing to CleanMyHuawei

Thank you for your interest in contributing to **CleanMyHuawei**!

CleanMyHuawei is built on a modular, multi-version architecture. While our baseline profile targets **EMUI 12**, Huawei devices across the globe operate on diverse software releases, including **EMUI 10**, **EMUI 11**, **HarmonyOS 2.0**, **HarmonyOS 3.0**, and **HarmonyOS 4.0**.

By submitting profiles for your specific software build, you help expand hardware support for users worldwide.

---

## Contribution Workflow (Git-Flow)

Adding support for a new operating system release follows a frictionless, four-step process:

```
Fork Repository ──► Dump Device Packages ──► Generate JSON Profile ──► Submit Pull Request
```

### Step 1: Fork and Clone

1. Fork the CleanMyHuawei repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/CleanMyHuawei.git
   cd CleanMyHuawei
   ```

### Step 2: Extract Your Live Device Baseline

Connect your phone with USB Debugging enabled, then identify your operating system slug and export your device packages:

```bash
# 1. Inspect detected platform and target profile slug
python3 clean.py --info

# 2. Export your installed packages to dumps/original_packages.txt
python3 clean.py --dump
```

Note the **Auto Profile Slug** displayed in the terminal output (for example: `emui_11` or `harmonyos_3`). Your new profile file must be named:
`profiles/<auto_profile_slug>.json` (e.g., `profiles/emui_11.json` or `profiles/harmonyos_3.json`).

---

### Step 3: Categorize Packages Using AI (`CONTRIBUTING_PROMPT.txt`)

Manually classifying 200+ Android packages can be tedious. To make profile generation effortless:

1. Open [CONTRIBUTING_PROMPT.txt](CONTRIBUTING_PROMPT.txt) located in the repository root.
2. Copy the prompt template.
3. Paste the contents of your `dumps/original_packages.txt` into the designated section at the bottom of the prompt.
4. Run the prompt through your preferred AI assistant (Codex, Claude Code, Antigravity, etc.).
5. Save the generated JSON output into:
   ```bash
   profiles/<auto_profile_slug>.json
   ```

#### Classification Rules:
- **`safe_to_remove`**: Third-party pre-installs (Amazon, Facebook, Booking), non-essential media storefronts, promotion tools, and harmless analytics.
- **`advanced_remove`**: Split into four structured sub-categories:
  - `analytics_and_tracking`: Recommendation daemons, telemetry, diagnostic loggers, Celia voice assistant.
  - `cloud_and_sync`: Huawei Cloud, Drive, Phone Clone, cloud sync adapters.
  - `theme_and_customization`: Huawei Theme engine and lockscreen styling frameworks.
  - `ecosystem_and_sharing`: Multi-Screen Collaboration, Huawei Share, PC Assistant, MeeTime.
- **`critical_keep`**: Core Android/EMUI framework (`android`, `systemui`, `settings`, `telecom`, `phone`, `packageinstaller`, `powergenie`, `launcher`). **Never** add essential system services to removal lists.

---

### Step 4: Verify Locally

Verify that your newly created profile is recognized and matches correctly on your device:

```bash
# 1. Run live comparison scan
python3 clean.py --scan

# 2. Perform a dry-run simulation (verifies no syntax or parsing errors)
python3 clean.py --mode safe --dry-run
```

---

### Step 5: Submit a Pull Request

1. Create a dedicated branch for your profile:
   ```bash
   git checkout -b profile/<auto_profile_slug>
   ```
2. Commit your new profile file:
   ```bash
   git add profiles/<auto_profile_slug>.json
   git commit -m "feat(profile): add debloat profile for <Device Model> (<OS Version>)"
   ```
3. Push your branch to GitHub and open a **Pull Request**:
   ```bash
   git push origin profile/<auto_profile_slug>
   ```

---

## Code Quality Standards

- Maintain documentation integrity: all code comments, docstrings, and CLI output strings must remain in English.
- Do not commit physical device serial numbers or personal data.
- Ensure all JSON profiles are valid JSON syntax without trailing commas.


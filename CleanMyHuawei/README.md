# CleanMyHuawei

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Android / EMUI / HarmonyOS](https://img.shields.io/badge/Platform-EMUI%20%7C%20HarmonyOS-red.svg)](https://consumer.huawei.com/)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](CONTRIBUTING.md)

CleanMyHuawei is an automated, open-source debloating and system optimization framework designed for Huawei and Honor smartphones running EMUI and HarmonyOS. It provides safe, reversible, and granular uninstallation of pre-installed bloatware, telemetry, and background services without requiring root access.

---

## Environment Note

The baseline configuration (`profiles/emui_12.json`) was extracted and categorized from a flagship Kirin 980 device running EMUI 12, ensuring high architectural compatibility across other EMUI 12 smartphones. The modular multi-version engine dynamically adapts to connected hardware and identifies missing profiles for newer or older software builds.

---

## Key Features

- **Safe Mode Debloat**: Uninstalls only verified third-party bloatware, advertisements, and non-essential telemetry without affecting core operating system integrity.
- **Full Bulk Removal**: Removes all safe and intermediate/medium-risk applications simultaneously in a single unified operation for maximum system decluttering.
- **Granular Interactive Advanced Mode**: Empowers users to selectively debloat specific subsystems—such as Analytics & Tracking, Cloud & Sync, or Theme Customization—or choose individual packages manually.
- **Smart Rollback & Reinstallation**: Restores missing system packages directly to the primary user via live ADB commands without requiring a factory reset.
- **Pre- & Post-Debloat RAM Telemetry**: Captures live memory snapshots (`dumpsys meminfo`) with a built-in system stabilization delay to accurately quantify reclaimed RAM.
- **Automated Restore Script Generation**: Exports an executable `dumps/restore.sh` alongside an inventory of uninstalled applications on every run.

---

## Quick Start Guide

### Prerequisites
1. **Python 3.8+** installed on your computer.
2. **Android Platform Tools (ADB)** installed and accessible in your system `PATH`.
3. **USB Debugging** enabled on your Huawei smartphone (*Settings > About Phone > Tap 'Build Number' 7 times > System & Updates > Developer Options > Enable USB Debugging*).

### Running the Suite

Connect your phone to your computer via USB, open a terminal, and execute:

```bash
cd ~/Desktop/CleanMyHuawei
python3 clean.py
```

### CLI Command Flags

For automated workflows or scripting, CleanMyHuawei supports direct flags:

```bash
python3 clean.py --info                                    # View device hardware model & OS build
python3 clean.py --ram                                     # Inspect live device memory metrics
python3 clean.py --dump                                    # Export installed package baseline to dumps/
python3 clean.py --scan                                    # Scan device and compare against active profile
python3 clean.py --mode safe --dry-run                     # Simulate Safe Mode debloat
python3 clean.py --mode safe                               # Execute Safe Mode debloat
python3 clean.py --mode advanced                           # Execute Full Bulk debloat
python3 clean.py --reinstall                               # Smart Rollback: Reinstall missing profile packages
```

---

## Community & Contributing

CleanMyHuawei is designed to scale across the entire Huawei ecosystem. If your device runs EMUI 10, EMUI 11, or HarmonyOS 2/3/4, you can contribute software profile templates to expand hardware coverage.

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for step-by-step instructions on creating, testing, and submitting new profile templates using our Git-flow process and AI-assisted prompt workflows.


#!/usr/bin/env python3
"""CleanMyHuawei - CLI Entrypoint & Development Suite.

An open-source, community-driven framework for safely debloating, optimizing,
benchmarking, and rolling back Huawei and Honor devices running EMUI and HarmonyOS.

Usage examples:
    python3 clean.py                          # Interactive Main Menu
    python3 clean.py --mode safe              # Direct Safe Mode debloat
    python3 clean.py --mode advanced          # Direct Advanced Mode (Bulk)
    python3 clean.py --reinstall              # Direct Smart Rollback (Reinstall Bloatware)
    python3 clean.py --ram                    # Direct RAM snapshot
    python3 clean.py --scan                   # Direct Package Scan
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from core.engine import DebloatMode, HuaweiEngine, ScanResult

BANNER = r"""
   _____ _                  __  __       _    _                            _ 
  / ____| |                |  \/  |     | |  | |                          (_)
 | |    | | ___  __ _ _ __ | \  / |_   _| |__| |_   _  __ ___      _____ _ 
 | |    | |/ _ \/ _` | '_ \| |\/| | | | |  __  | | | |/ _` \ \ /\ / / _ \ |
 | |____| |  __/ (_| | | | | |  | | |_| | |  | | |_| | (_| |\ V  V /  __/ |
  \_____|_|\___|\__,_|_| |_|_|  |_|\__, |_|  |_|\__,_|\__,_| \_/\_/ \___|_|
                                    __/ |                                  
                                   |___/    Community Edition v2.1
"""


def parse_arguments() -> argparse.Namespace:
    """Configure and parse CLI command-line flags."""
    parser = argparse.ArgumentParser(
        description="CleanMyHuawei: Open-source debloating & optimization suite for Huawei/Honor devices."
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Display connected device details, OS version, and detected profile slug.",
    )
    parser.add_argument(
        "--ram",
        action="store_true",
        help="Query and display current live RAM usage and memory status via dumpsys meminfo.",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Export current installed packages to dumps/original_packages.txt for baseline backup.",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan live device packages and match against the appropriate profile rules.",
    )
    parser.add_argument(
        "--mode",
        choices=["safe", "advanced"],
        default=None,
        help="Directly run debloat engine in specified mode: 'safe' or 'advanced'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate removal commands without actually uninstalling any package from the device.",
    )
    parser.add_argument(
        "--reinstall",
        action="store_true",
        help="Smart Rollback: Reinstall missing profile packages back onto the connected phone.",
    )
    parser.add_argument(
        "--settle-delay",
        type=int,
        default=0,
        help="Optional cooldown delay (in seconds) to let background daemons settle before measuring RAM.",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Bypass interactive user confirmation prompt after debloating.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Specify an explicit profile JSON filename located in profiles/ (e.g., emui_12.json).",
    )
    return parser.parse_args()


# =============================================================================
# Interactive Menus: Main Menu, Debloat Menu, Advanced Menu, Developer Options
# =============================================================================

def prompt_main_menu() -> str:
    """Display the top-level Main Menu."""
    print("=" * 65)
    print("  MAIN MENU")
    print("=" * 65)
    print("  [1] Run Debloat Engine (Safe / Advanced)")
    print("  [2] Developer Options")
    print("  [3] Exit")
    print("-" * 65)
    return input("Select an option (1-3): ").strip()


def prompt_debloat_submenu() -> str:
    """Display Debloat Engine configuration choices."""
    print("\n" + "=" * 65)
    print("  DEBLOAT ENGINE CONFIGURATION")
    print("=" * 65)
    print("  [1] Safe Mode Debloat        : Removes only non-essential & telemetry bloat")
    print("  [2] Advanced Mode Debloat    : Medium-risk apps & ecosystem services (Modular)")
    print("  [3] Dry Run (Safe Mode)      : Simulation only (no device changes)")
    print("  [4] Back to Main Menu")
    print("-" * 65)
    return input("Select an option (1-4): ").strip()


def prompt_advanced_mode_menu(scan_result: ScanResult) -> Optional[List[str]]:
    """Display granular and bulk selection options for Advanced Mode debloating."""
    print("\n" + "=" * 65)
    print("  ADVANCED MODE: MEDIUM-RISK APPLICATION SELECTION")
    print("=" * 65)
    print("Select debloat strategy (single choice or comma-separated, e.g., '2,4'):\n")
    print("  [1] Remove All Safe & Medium-Risk Applications Directly (Full Bulk Removal)")
    print("  [2] Remove Analytics & Tracking Services Only")
    print("  [3] Remove Cloud & Sync Services Only")
    print("  [4] Remove Theme & Customization Services Only")
    print("  [5] Select individual packages manually from a list")
    print("  [6] Cancel / Back to Previous Menu")
    print("-" * 65)

    selection = input("Enter your choice: ").strip()
    if selection == "6" or not selection:
        return None

    subcats = scan_result.advanced_subcategories
    analytics_pkgs = subcats.get("analytics_and_tracking", None)
    cloud_pkgs = subcats.get("cloud_and_sync", None)
    theme_pkgs = subcats.get("theme_and_customization", None)

    # 1. Full Bulk Removal (Everything that is safe + all intermediate/medium-risk categories)
    if "1" in [s.strip() for s in selection.split(",")]:
        targets = sorted(list(set(scan_result.targets_safe_to_remove + scan_result.targets_advanced_remove)))
        print(
            f"\n[+] Selected: Full Bulk Removal ({len(targets)} total active packages: "
            f"{len(scan_result.targets_safe_to_remove)} safe + {len(scan_result.targets_advanced_remove)} intermediate)"
        )
        return targets

    # 5. Manual Selection from List
    if "5" in [s.strip() for s in selection.split(",")]:
        all_active = list(scan_result.targets_advanced_remove)
        if not all_active:
            print("[-] No medium-risk packages detected on this device.")
            return None

        print("\nActive Medium-Risk Packages on your phone:")
        for idx, pkg in enumerate(all_active, start=1):
            print(f"  [{idx:2d}] {pkg}")
        print("-" * 65)
        raw_indexes = input("Enter package numbers to remove (e.g., '1,3,5'): ").strip()
        selected_manual = []
        for token in raw_indexes.split(","):
            token = token.strip()
            if token.isdigit():
                i = int(token) - 1
                if 0 <= i < len(all_active):
                    selected_manual.append(all_active[i])
        return selected_manual

    # 2, 3, 4 Combinations
    chosen_targets: Set[str] = set()
    tokens = [s.strip() for s in selection.split(",")]

    for t in tokens:
        if t == "2" and analytics_pkgs:
            chosen_targets.update(analytics_pkgs.live_matched_packages)
            print(f"  [+] Included: Analytics & Tracking ({len(analytics_pkgs.live_matched_packages)} packages)")
        elif t == "3" and cloud_pkgs:
            chosen_targets.update(cloud_pkgs.live_matched_packages)
            print(f"  [+] Included: Cloud & Sync ({len(cloud_pkgs.live_matched_packages)} packages)")
        elif t == "4" and theme_pkgs:
            chosen_targets.update(theme_pkgs.live_matched_packages)
            print(f"  [+] Included: Theme & Customization ({len(theme_pkgs.live_matched_packages)} packages)")

    return sorted(list(chosen_targets))


def prompt_developer_submenu() -> str:
    """Display Developer Options submenu."""
    print("\n" + "=" * 65)
    print("  DEVELOPER OPTIONS")
    print("=" * 65)
    print("  [1] Reinstall Bloatware      : Smart Rollback (reinstall missing profile apps)")
    print("  [2] Inspect Device Memory    : Live RAM snapshot (dumpsys meminfo)")
    print("  [3] Backup Live Packages     : Export installed package list to dumps/")
    print("  [4] Device Diagnostics       : View hardware model & OS build properties")
    print("  [5] Back to Main Menu")
    print("-" * 65)
    return input("Select an option (1-5): ").strip()


# =============================================================================
# Execution Routines
# =============================================================================

def run_debloat_flow(
    engine: HuaweiEngine,
    mode: DebloatMode,
    custom_targets: Optional[List[str]] = None,
    dry_run: bool = False,
    settle_delay: int = 0,
    wait_confirmation: bool = True,
    profile_override: str = None,
) -> bool:
    """Scan device and execute the chosen debloat mode with stabilization."""
    profile_path = None
    if profile_override:
        profile_path = engine.profiles_dir / profile_override

    scan_result = engine.scan_and_match(profile_path=profile_path)
    if not scan_result:
        return False

    engine.print_scan_report(scan_result)

    # Determine targets to confirm
    if custom_targets is not None:
        targets_to_remove = [p for p in custom_targets if p not in scan_result.protected_critical]
    elif mode == DebloatMode.SAFE:
        targets_to_remove = list(scan_result.targets_safe_to_remove)
    else:
        targets_to_remove = list(scan_result.targets_safe_to_remove) + list(scan_result.targets_advanced_remove)

    if not targets_to_remove:
        print("[✓] No target packages matching your criteria are currently installed.")
        return True

    if not dry_run:
        prompt_msg = (
            f"\n⚠️  CONFIRMATION: You are about to uninstall {len(targets_to_remove)} package(s) on your physical device.\n"
            f"   (Data will be kept using -k, and a restore.sh script will be generated).\n"
            f"   Are you sure you want to proceed? [y/N]: "
        )
        confirm = input(prompt_msg).strip().lower()
        if confirm not in ("y", "yes"):
            print("[*] Debloat aborted by user.")
            return False

    engine.execute_debloat(
        scan_result=scan_result,
        mode=mode,
        custom_targets=targets_to_remove,
        dry_run=dry_run,
        settle_delay=settle_delay,
        wait_confirmation=wait_confirmation,
    )
    return True


def run_developer_options(engine: HuaweiEngine, profile_override: str = None) -> None:
    """Interactive loop for the Developer Options submenu."""
    while True:
        choice = prompt_developer_submenu()

        if choice == "1":
            profile_path = (engine.profiles_dir / profile_override) if profile_override else None
            engine.reinstall_profile_bloatware(profile_path=profile_path)

        elif choice == "2":
            print("\n[*] Fetching live device memory metrics (adb shell dumpsys meminfo)...")
            mem = engine.get_memory_snapshot()
            if mem:
                print("\n" + "=" * 55)
                print("  LIVE MEMORY TELEMETRY")
                print("=" * 55)
                print(f"[*] Total Physical RAM   : {mem.total_ram_mb:,.2f} MB")
                print(f"[*] Active Used RAM      : {mem.used_ram_mb:,.2f} MB")
                print(f"[*] Available Free RAM   : {mem.free_ram_mb:,.2f} MB")
                usage_pct = (mem.used_ram_mb / mem.total_ram_mb) * 100
                print(f"[*] Current RAM Usage    : {usage_pct:.1f}%")
                print("=" * 55 + "\n")

        elif choice == "3":
            engine.dump_original_packages()

        elif choice == "4":
            device = engine.identify_device()
            if device:
                print("\n" + "=" * 55)
                print("  DEVICE DIAGNOSTICS")
                print("=" * 55)
                print(f"[*] Serial Number      : {device.serial}")
                print(f"[*] Hardware Model     : {device.model}")
                print(f"[*] Platform / OS      : {device.os_family} {device.major_version or 'N/A'}")
                print(f"[*] Raw Version String : {device.emui_version_raw}")
                print(f"[*] Matched Profile    : {device.profile_slug}.json")
                print("=" * 55 + "\n")

        elif choice == "5":
            break
        else:
            print("[!] Invalid selection. Please enter a number between 1 and 5.")


def main() -> int:
    """Main CLI execution flow."""
    print(BANNER)
    args = parse_arguments()
    engine = HuaweiEngine()

    # 1. Verify ADB connection
    if not engine.is_device_connected():
        return 1

    # 2. Inspect device info
    device = engine.identify_device()
    if not device:
        print("[-] Failed to retrieve device identification parameters.")
        return 1

    print(f"[*] Connected Device   : {device.model} ({device.serial})")
    print(f"[*] Detected Platform  : {device.os_family} {device.major_version or 'N/A'}")
    print(f"[*] Active Profile Slug: {device.profile_slug}")

    # =========================================================================
    # Direct CLI Flag Handling (Non-Interactive / Scripting)
    # =========================================================================
    if args.info:
        return 0

    if args.ram:
        mem = engine.get_memory_snapshot()
        if mem:
            print(f"[*] RAM: {mem.used_ram_mb:,.2f} MB used / {mem.total_ram_mb:,.2f} MB total")
        return 0

    if args.dump:
        engine.dump_original_packages()
        return 0

    if args.reinstall:
        profile_path = (engine.profiles_dir / args.profile) if args.profile else None
        engine.reinstall_profile_bloatware(profile_path=profile_path)
        return 0

    if args.scan:
        profile_path = (engine.profiles_dir / args.profile) if args.profile else None
        scan_res = engine.scan_and_match(profile_path=profile_path)
        if scan_res:
            engine.print_scan_report(scan_res)
        return 0

    if args.mode:
        selected_mode = DebloatMode(args.mode)
        run_debloat_flow(
            engine=engine,
            mode=selected_mode,
            dry_run=args.dry_run,
            settle_delay=args.settle_delay,
            wait_confirmation=(not args.no_pause),
            profile_override=args.profile,
        )
        return 0

    # =========================================================================
    # Interactive Main Menu Loop
    # =========================================================================
    while True:
        main_choice = prompt_main_menu()

        if main_choice == "1":
            debloat_choice = prompt_debloat_submenu()

            if debloat_choice == "1":
                run_debloat_flow(
                    engine, DebloatMode.SAFE, dry_run=False,
                    settle_delay=args.settle_delay, wait_confirmation=(not args.no_pause),
                    profile_override=args.profile
                )

            elif debloat_choice == "2":
                # Modular Advanced Selection Menu
                scan_res = engine.scan_and_match(
                    profile_path=(engine.profiles_dir / args.profile) if args.profile else None
                )
                if not scan_res:
                    continue

                chosen_advanced_targets = prompt_advanced_mode_menu(scan_res)
                if not chosen_advanced_targets:
                    print("[*] Advanced selection cancelled.")
                    continue

                # Prompt user for Dry Run vs. Live Removal
                print("\nExecution Mode for Advanced Selection:")
                print("  [1] Live Removal (Execute on physical device)")
                print("  [2] Dry Run Simulation (Inspect commands only)")
                exec_choice = input("Select (1-2) [default: 1]: ").strip()
                is_dry = (exec_choice == "2")

                run_debloat_flow(
                    engine,
                    mode=DebloatMode.CUSTOM,
                    custom_targets=chosen_advanced_targets,
                    dry_run=is_dry,
                    settle_delay=args.settle_delay,
                    wait_confirmation=(not args.no_pause),
                    profile_override=args.profile,
                )

            elif debloat_choice == "3":
                run_debloat_flow(
                    engine, DebloatMode.SAFE, dry_run=True,
                    settle_delay=args.settle_delay, wait_confirmation=(not args.no_pause),
                    profile_override=args.profile
                )

            elif debloat_choice == "4":
                continue
            else:
                print("[!] Invalid debloat selection.")

        elif main_choice == "2":
            run_developer_options(engine, profile_override=args.profile)

        elif main_choice == "3":
            print("\n[*] Exiting CleanMyHuawei. Have a great day!")
            break
        else:
            print("[!] Invalid selection. Please choose 1, 2, or 3.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""CleanMyHuawei - Core Engine.

An open-source, community-driven debloating and optimization framework
tailored for Huawei and Honor devices running EMUI and HarmonyOS.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class DebloatMode(str, Enum):
    """Supported debloat operational modes."""
    SAFE = "safe"
    ADVANCED = "advanced"
    CUSTOM = "custom"


@dataclass
class DeviceInfo:
    """Represents detected hardware and operating system parameters."""
    serial: str
    model: str
    emui_version_raw: str
    os_family: str  # e.g., "EMUI", "HarmonyOS", "MagicUI", "Android"
    major_version: Optional[str]  # e.g., "12", "11", "3"
    profile_slug: str  # e.g., "emui_12", "harmonyos_3"


@dataclass
class AdvancedCategoryMatch:
    """Represents a categorized subset of medium-risk packages present on the device."""
    key: str
    name: str
    description: str
    all_defined_packages: List[str]
    live_matched_packages: List[str]


@dataclass
class ScanResult:
    """Encapsulates the results of matching live device packages against a profile."""
    profile_name: str
    total_live_packages: int
    targets_safe_to_remove: List[str] = field(default_factory=list)
    targets_advanced_remove: List[str] = field(default_factory=list)
    advanced_subcategories: Dict[str, AdvancedCategoryMatch] = field(default_factory=dict)
    protected_critical: List[str] = field(default_factory=list)
    unclassified_installed: List[str] = field(default_factory=list)
    profile_rules_missing_on_device: List[str] = field(default_factory=list)


@dataclass
class MemorySnapshot:
    """Stores a point-in-time RAM snapshot parsed from dumpsys meminfo."""
    total_ram_mb: float
    used_ram_mb: float
    free_ram_mb: float
    raw_timestamp: Optional[str] = None


@dataclass
class DebloatSummary:
    """Stores the execution results of a debloat process."""
    mode: DebloatMode
    dry_run: bool
    total_targeted: int
    successful: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    restore_script_path: Optional[Path] = None
    initial_memory: Optional[MemorySnapshot] = None
    post_memory: Optional[MemorySnapshot] = None


@dataclass
class RestoreSummary:
    """Stores the results of the smart package reinstallation process."""
    total_profile_packages: int
    already_installed: List[str] = field(default_factory=list)
    successfully_restored: List[str] = field(default_factory=list)
    failed_to_restore: List[str] = field(default_factory=list)


class HuaweiEngine:
    """Core device communication, identification, and debloating engine."""

    def __init__(self, workspace_root: Optional[Path] = None):
        """Initialize workspace paths and repository layout.

        Args:
            workspace_root: Base project path. Defaults to repository root.
        """
        self.workspace_root = workspace_root or Path(__file__).resolve().parent.parent
        self.dumps_dir = self.workspace_root / "dumps"
        self.profiles_dir = self.workspace_root / "profiles"

    def _run_adb(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        """Execute an ADB command with standardized error handling.

        Args:
            args: Command arguments passed to ADB.

        Returns:
            CompletedProcess instance with captured output.
        """
        command = ["adb"] + args
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False
            )
        except FileNotFoundError:
            print("[!] Error: 'adb' executable not found in system PATH.")
            print("[i] Please install Android Platform Tools and ensure ADB is accessible.")
            sys.exit(1)

    def get_connected_device_serial(self) -> Optional[str]:
        """Detect the first authorized connected Android/Huawei device.

        Returns:
            The device serial number if attached and authorized, else None.
        """
        result = self._run_adb(["devices"])
        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]

        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                return parts[0]

        return None

    def is_device_connected(self) -> bool:
        """Verify device connectivity and print status."""
        serial = self.get_connected_device_serial()
        if not serial:
            print("[-] No authorized device detected via ADB.")
            print("[i] Connect your phone via USB and enable USB Debugging in Developer Options.")
            return False

        print(f"[+] Device connected: {serial}")
        return True

    def get_device_property(self, prop_name: str) -> str:
        """Fetch a system property via getprop."""
        result = self._run_adb(["shell", "getprop", prop_name])
        return result.stdout.strip()

    def identify_device(self) -> Optional[DeviceInfo]:
        """Detect device model, OS family (EMUI/HarmonyOS), and version.

        Dynamically resolves the profile slug for modular profile loading.

        Returns:
            Populated DeviceInfo instance, or None if detection failed.
        """
        serial = self.get_connected_device_serial()
        if not serial:
            return None

        model = self.get_device_property("ro.product.model") or "Huawei Device"

        emui_raw = (
            self.get_device_property("ro.build.version.emui")
            or self.get_device_property("hw_sc.build.platform.version")
            or self.get_device_property("ro.huawei.build.display.id")
            or self.get_device_property("ro.build.display.id")
        )

        harmony_version = self.get_device_property("hw_sc.build.os.enable")
        harmony_display = self.get_device_property("ro.harmonyos.version")

        # Determine OS family & version
        os_family = "EMUI"
        major_version = None

        if emui_raw and ("emui" in emui_raw.lower() or "emotionui" in emui_raw.lower()):
            os_family = "EMUI"
            match = re.search(r"(?:EmotionUI|EMUI)[_\s-]*(\d+)", emui_raw, re.IGNORECASE)
            if match:
                major_version = match.group(1)
        elif harmony_display or (harmony_version and harmony_version.lower() == "true"):
            os_family = "HarmonyOS"
            if harmony_display:
                match = re.search(r"(\d+(\.\d+)?)", harmony_display)
                if match:
                    major_version = match.group(1).split(".")[0]
        elif emui_raw and "magic" in emui_raw.lower():
            os_family = "MagicUI"
            match = re.search(r"MagicUI[_\s-]*(\d+)", emui_raw, re.IGNORECASE)
            if match:
                major_version = match.group(1)
        else:
            os_family = "Android"
            android_ver = self.get_device_property("ro.build.version.release")
            if android_ver:
                major_version = android_ver.split(".")[0]

        profile_slug = f"{os_family.lower()}_{major_version}" if major_version else "generic"

        return DeviceInfo(
            serial=serial,
            model=model,
            emui_version_raw=emui_raw,
            os_family=os_family,
            major_version=major_version,
            profile_slug=profile_slug,
        )

    # =========================================================================
    # Step 5: Memory Tracking & Stabilization Logic
    # =========================================================================

    def get_memory_snapshot(self) -> Optional[MemorySnapshot]:
        """Capture a live RAM usage snapshot from the device using dumpsys meminfo.

        Parses Total RAM, Free RAM, and Used RAM in Megabytes.

        Returns:
            MemorySnapshot instance, or None if the query fails.
        """
        result = self._run_adb(["shell", "dumpsys", "meminfo"])
        if result.returncode != 0 or not result.stdout:
            print("[-] Warning: Failed to query device memory info via dumpsys.")
            return None

        total_kb = None
        free_kb = None
        used_kb = None

        for line in result.stdout.splitlines():
            line_str = line.strip()
            if "Total RAM:" in line_str and total_kb is None:
                match = re.search(r"Total RAM:\s*([\d,]+)K", line_str)
                if match:
                    total_kb = int(match.group(1).replace(",", ""))
            elif "Free RAM:" in line_str and free_kb is None:
                match = re.search(r"Free RAM:\s*([\d,]+)K", line_str)
                if match:
                    free_kb = int(match.group(1).replace(",", ""))
            elif "Used RAM:" in line_str and used_kb is None:
                match = re.search(r"Used RAM:\s*([\d,]+)K", line_str)
                if match:
                    used_kb = int(match.group(1).replace(",", ""))

        if total_kb is not None and used_kb is not None:
            total_mb = round(total_kb / 1024.0, 2)
            used_mb = round(used_kb / 1024.0, 2)
            free_mb = round((free_kb / 1024.0) if free_kb else (total_mb - used_mb), 2)

            return MemorySnapshot(
                total_ram_mb=total_mb,
                used_ram_mb=used_mb,
                free_ram_mb=free_mb,
            )

        return None

    def wait_for_system_stabilization(
        self, delay_seconds: int = 0, interactive_confirm: bool = True
    ) -> None:
        """Pause execution to allow Android background services and GC to stabilize.

        Prevents 'system shock' memory spikes immediately following multiple package
        uninstalls from skewing post-debloat telemetry.

        Args:
            delay_seconds: Configurable sleep cooldown in seconds.
            interactive_confirm: Whether to prompt the user before capturing memory.
        """
        print("\n" + "-" * 65)
        print("⏳ SYSTEM STABILIZATION & COOL-DOWN")
        print("   Following uninstalls, the Android framework terminates dependent")
        print("   threads, runs internal garbage collection, and adjusts cache pools.")
        print("-" * 65)

        if delay_seconds > 0:
            print(f"[*] Applying automated cool-down delay: {delay_seconds} seconds...")
            time.sleep(delay_seconds)

        if interactive_confirm:
            print("[i] Check your phone screen or give the device a few moments to settle.")
            input("👉 Has the system stabilized? Press [Enter] to capture final RAM numbers...")

        print("[*] Capturing post-debloat memory snapshot...\n")

    def display_optimization_report(
        self,
        initial_mem: Optional[MemorySnapshot],
        post_mem: Optional[MemorySnapshot],
        removed_packages_count: int,
        mode_label: str,
        dry_run: bool = False,
    ) -> None:
        """Display an open-source, human-readable RAM optimization report."""
        print("\n" + "=" * 65)
        print("  CLEANMYHUAWEI - SYSTEM OPTIMIZATION & RAM REPORT")
        print("=" * 65)
        print(f"[*] Operation Mode           : {mode_label.upper()}")
        print(f"[*] Execution Type           : {'SIMULATION (DRY RUN)' if dry_run else 'LIVE DEBLOAT'}")
        print(f"[+] Total Packages Removed   : {removed_packages_count}")
        print("-" * 65)

        if initial_mem and post_mem and not dry_run:
            initial_used = initial_mem.used_ram_mb
            post_used = post_mem.used_ram_mb
            freed_mb = round(initial_used - post_used, 2)
            freed_str = f"+{freed_mb} MB" if freed_mb >= 0 else f"{freed_mb} MB"

            print(f"[*] Total Physical RAM       : {initial_mem.total_ram_mb:,.2f} MB")
            print(f"[*] Baseline RAM Usage       : {initial_used:,.2f} MB")
            print(f"[*] Post-Debloat RAM Usage   : {post_used:,.2f} MB")
            print(f"[✓] Total Freed Memory       : {freed_str}")
            print("-" * 65)

            if freed_mb > 0:
                print(f"🚀 Optimization Result: Successfully recovered {freed_mb} MB of active RAM.")
                print("   More headroom is now available for local AI models, apps, and multitasking.")
            else:
                print("ℹ️  Note: System caches were dynamically allocated or background services settled.")
                print("   Rebooting the phone will fully reflect cold memory footprint savings.")
        elif initial_mem and dry_run:
            print(f"[*] Total Physical RAM       : {initial_mem.total_ram_mb:,.2f} MB")
            print(f"[*] Baseline RAM Usage       : {initial_mem.used_ram_mb:,.2f} MB")
            print("[i] Dry Run Mode             : Physical RAM changes are simulated.")
        else:
            print("[i] Memory telemetry unavailable for this run.")

        print("=" * 65 + "\n")

    # =========================================================================
    # Live Package Fetching & Categorized Profile Matching
    # =========================================================================

    def fetch_live_packages(self) -> Set[str]:
        """Query currently installed packages directly from the physical phone in real time.

        Returns:
            A set of installed package names without the 'package:' prefix.
        """
        print("[*] Fetching live package list from device (adb shell pm list packages)...")
        result = self._run_adb(["shell", "pm", "list", "packages"])
        if result.returncode != 0:
            print(f"[-] Failed to fetch package list: {result.stderr.strip()}")
            return set()

        packages: Set[str] = set()
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if line.startswith("package:"):
                pkg_name = line[len("package:"):].strip()
                if pkg_name:
                    packages.add(pkg_name)

        print(f"[+] Total live packages currently installed: {len(packages)}")
        return packages

    def dump_original_packages(self, filename: str = "original_packages.txt") -> Optional[Path]:
        """Export live packages to dumps/<filename> for baseline backup."""
        self.dumps_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.dumps_dir / filename

        packages = sorted(list(self.fetch_live_packages()))
        if not packages:
            print("[-] Unable to create backup: No package list returned by device.")
            return None

        formatted = [f"package:{pkg}" for pkg in packages]
        target_path.write_text("\n".join(formatted) + "\n", encoding="utf-8")
        print(f"[+] Original package list dumped to: {target_path}")
        return target_path

    def resolve_profile_path(self, requested_profile: Optional[str] = None) -> Optional[Path]:
        """Resolve profile path dynamically based on device OS or user override.

        Args:
            requested_profile: Optional custom profile filename (e.g., 'emui_12.json').

        Returns:
            Path to the verified profile JSON, or None if missing.
        """
        if requested_profile:
            candidate = self.profiles_dir / requested_profile
            if candidate.exists():
                return candidate
            print(f"[-] Specified profile file not found: {candidate}")
            return None

        device = self.identify_device()
        if not device:
            print("[-] Cannot resolve profile: No active device found.")
            return None

        candidate_name = f"{device.profile_slug}.json"
        candidate_path = self.profiles_dir / candidate_name

        if candidate_path.exists():
            return candidate_path

        print("\n" + "=" * 65)
        print("  COMMUNITY PROFILE CONTRIBUTION NEEDED")
        print("=" * 65)
        print(f"[*] Detected Device : {device.model} ({device.serial})")
        print(f"[*] Operating System: {device.os_family} {device.major_version or 'Unknown'}")
        print(f"[-] Profile Missing : 'profiles/{candidate_name}' does not exist yet.")
        print("-" * 65)
        print("💡 CleanMyHuawei is a community-driven open-source project!")
        print(f"   You can easily contribute by creating 'profiles/{candidate_name}'.")
        print("   Use 'profiles/emui_12.json' as a baseline reference template.")
        print("   Feel free to submit a Pull Request on GitHub to help other users.")
        print("=" * 65 + "\n")
        return None

    def load_profile(self, profile_path: Path) -> Optional[Dict[str, Any]]:
        """Load and parse profile JSON."""
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[-] Failed to parse profile '{profile_path.name}': {e}")
            return None

    def scan_and_match(self, profile_path: Optional[Path] = None) -> Optional[ScanResult]:
        """Scan real-time packages on device and categorize against profile rules.

        Supports both granular sub_categories in advanced_remove and legacy flat lists.

        Args:
            profile_path: Path to profile JSON. If None, resolves dynamically.

        Returns:
            ScanResult containing categorized package groups.
        """
        resolved_path = profile_path or self.resolve_profile_path()
        if not resolved_path:
            return None

        profile_data = self.load_profile(resolved_path)
        if not profile_data:
            return None

        live_packages = self.fetch_live_packages()
        if not live_packages:
            return None

        categories = profile_data.get("categories", {})
        rule_safe = set(categories.get("safe_to_remove", {}).get("packages", []))
        rule_critical = set(categories.get("critical_keep", {}).get("packages", []))

        # Parse modular advanced_remove (sub-categories vs flat list)
        advanced_data = categories.get("advanced_remove", {})
        advanced_subcats: Dict[str, AdvancedCategoryMatch] = {}
        all_advanced_packages: Set[str] = set()

        if "sub_categories" in advanced_data:
            for sub_key, sub_val in advanced_data["sub_categories"].items():
                def_pkgs = sub_val.get("packages", [])
                matched = sorted(list(live_packages & set(def_pkgs)))
                all_advanced_packages.update(def_pkgs)
                advanced_subcats[sub_key] = AdvancedCategoryMatch(
                    key=sub_key,
                    name=sub_val.get("name", sub_key.replace("_", " ").title()),
                    description=sub_val.get("description", ""),
                    all_defined_packages=def_pkgs,
                    live_matched_packages=matched,
                )
        elif "packages" in advanced_data:
            def_pkgs = advanced_data["packages"]
            matched = sorted(list(live_packages & set(def_pkgs)))
            all_advanced_packages.update(def_pkgs)
            advanced_subcats["general_advanced"] = AdvancedCategoryMatch(
                key="general_advanced",
                name="General Advanced",
                description=advanced_data.get("description", ""),
                all_defined_packages=def_pkgs,
                live_matched_packages=matched,
            )

        all_rules = rule_safe | all_advanced_packages | rule_critical

        # Strictly dynamic set operations on physical packages
        matched_safe = sorted(list(live_packages & rule_safe))
        matched_advanced = sorted(list(live_packages & all_advanced_packages))
        matched_critical = sorted(list(live_packages & rule_critical))
        unclassified = sorted(list(live_packages - all_rules))
        missing_on_device = sorted(list(all_rules - live_packages))

        return ScanResult(
            profile_name=profile_data.get("profile_name", resolved_path.name),
            total_live_packages=len(live_packages),
            targets_safe_to_remove=matched_safe,
            targets_advanced_remove=matched_advanced,
            advanced_subcategories=advanced_subcats,
            protected_critical=matched_critical,
            unclassified_installed=unclassified,
            profile_rules_missing_on_device=missing_on_device,
        )

    def print_scan_report(self, result: ScanResult) -> None:
        """Display an open-source friendly scanning summary in English."""
        print("\n" + "=" * 65)
        print("  CLEANMYHUAWEI - LIVE SCAN & COMPARISON REPORT")
        print(f"  Profile: {result.profile_name}")
        print("=" * 65)
        print(f"[*] Total Installed Packages (Live)            : {result.total_live_packages}")
        print(f"[+] Present & Safe to Remove (safe_to_remove)  : {len(result.targets_safe_to_remove)}")
        print(f"[!] Present & Medium-Risk (advanced_remove)    : {len(result.targets_advanced_remove)}")
        for key, match in result.advanced_subcategories.items():
            print(f"    ├─ {match.name:<33}: {len(match.live_matched_packages)} active")
        print(f"[#] Protected System Packages (critical_keep)  : {len(result.protected_critical)}")
        print(f"[?] Unclassified / Other Installed Packages    : {len(result.unclassified_installed)}")
        print("-" * 65)

        print("\n>>> TARGET LIST: Verified safe packages on this device (safe_to_remove):")
        if result.targets_safe_to_remove:
            for pkg in result.targets_safe_to_remove:
                print(f"  [+] {pkg}")
        else:
            print("  (None found or already debloated)")

        print("\n>>> MEDIUM-RISK BREAKDOWN (advanced_remove sub-categories):")
        for key, match in result.advanced_subcategories.items():
            print(f"\n  • {match.name} ({len(match.live_matched_packages)} detected on device):")
            if match.live_matched_packages:
                for pkg in match.live_matched_packages:
                    print(f"    [!] {pkg}")
            else:
                print("    (None installed on this device)")

        print("\n" + "=" * 65 + "\n")

    # =========================================================================
    # Step 4: Removal Engine
    # =========================================================================

    def uninstall_package(self, package_name: str, dry_run: bool = False) -> bool:
        """Safely uninstalls a package for the primary user (User 0) while keeping app cache.

        Uses: adb shell pm uninstall -k --user 0 <package_name>

        Args:
            package_name: The Android package ID to uninstall.
            dry_run: If True, simulates the action without executing ADB uninstallation.

        Returns:
            True if uninstallation succeeded (or simulated), False otherwise.
        """
        command_args = ["shell", "pm", "uninstall", "-k", "--user", "0", package_name]
        command_str = f"adb {' '.join(command_args)}"

        if dry_run:
            print(f"  [SIMULATED] Would execute: {command_str}")
            return True

        result = self._run_adb(command_args)
        output = result.stdout.strip()

        if "Success" in output:
            print(f"  [✓] Uninstalled: {package_name}")
            return True

        err = result.stderr.strip() or output
        print(f"  [✗] Failed to uninstall {package_name}: {err}")
        return False

    def generate_restore_script(
        self, removed_packages: List[str], script_filename: str = "restore.sh"
    ) -> Path:
        """Generates an automated, one-click shell script to reinstall removed packages.

        Restore command used: adb shell pm install-existing --user 0 <package_name>

        Args:
            removed_packages: List of packages that were removed.
            script_filename: Target restore script file in dumps/.

        Returns:
            Path to the generated restore script.
        """
        self.dumps_dir.mkdir(parents=True, exist_ok=True)
        restore_path = self.dumps_dir / script_filename

        content_lines = [
            "#!/usr/bin/env bash",
            "# CleanMyHuawei - Auto-generated Restore Script",
            f"# Generated for {len(removed_packages)} uninstalled packages.",
            "# Run this script to restore any removed packages back to your Huawei device.",
            "",
            "set -e",
            'echo "=== Restoring Packages to Huawei Device ==="',
            "",
        ]

        for pkg in removed_packages:
            content_lines.append(f'echo "Restoring {pkg}..."')
            content_lines.append(f"adb shell pm install-existing --user 0 {pkg} || true")

        content_lines.append("")
        content_lines.append('echo "[✓] Restoration process finished successfully!"')
        content_lines.append("")

        restore_path.write_text("\n".join(content_lines), encoding="utf-8")
        restore_path.chmod(0o755)
        return restore_path

    def execute_debloat(
        self,
        scan_result: ScanResult,
        mode: DebloatMode = DebloatMode.SAFE,
        custom_targets: Optional[List[str]] = None,
        dry_run: bool = False,
        settle_delay: int = 0,
        wait_confirmation: bool = True,
    ) -> DebloatSummary:
        """Executes the secure debloating workflow with integrated stabilization & RAM telemetry.

        Supports predefined modes (Safe/Advanced) or dynamic custom lists from sub-category selections.

        Args:
            scan_result: Live comparison scan results.
            mode: DebloatMode.SAFE, DebloatMode.ADVANCED, or DebloatMode.CUSTOM.
            custom_targets: Explicit package list to process (used by Advanced sub-categories).
            dry_run: If True, simulates actions without modifying the device.
            settle_delay: Optional automated cooldown pause in seconds.
            wait_confirmation: Whether to prompt user to confirm system stabilization.

        Returns:
            DebloatSummary with performance metrics, successful, failed, and restore assets.
        """
        print("\n[*] Measuring baseline device RAM usage (adb shell dumpsys meminfo)...")
        initial_mem = self.get_memory_snapshot()
        if initial_mem:
            print(f"[+] Baseline RAM: {initial_mem.used_ram_mb:,.2f} MB used / {initial_mem.total_ram_mb:,.2f} MB total")

        if custom_targets is not None:
            targets = list(custom_targets)
            mode_label = f"{mode.value.upper()} SELECTION ({len(targets)} packages)"
        elif mode == DebloatMode.SAFE:
            targets = list(scan_result.targets_safe_to_remove)
            mode_label = "SAFE MODE (safe_to_remove only)"
        else:
            targets = list(scan_result.targets_safe_to_remove) + list(scan_result.targets_advanced_remove)
            mode_label = "ADVANCED FULL BULK (safe_to_remove + advanced_remove)"

        # Safety Check: Guarantee critical packages are never touched
        critical_set = set(scan_result.protected_critical)
        targets = [pkg for pkg in targets if pkg not in critical_set]

        print("\n" + "=" * 65)
        if dry_run:
            print(f"  DRY RUN SIMULATION - {mode_label}")
            print("  (No changes will be applied to your physical device)")
        else:
            print(f"  EXECUTING SECURE DEBLOAT - {mode_label}")
        print("=" * 65)
        print(f"[*] Target Packages to Process: {len(targets)}")
        print("-" * 65)

        successful: List[str] = []
        failed: List[str] = []

        for index, pkg in enumerate(targets, start=1):
            prefix = f"[{index}/{len(targets)}]"
            print(f"{prefix} Processing {pkg}...")
            if self.uninstall_package(pkg, dry_run=dry_run):
                successful.append(pkg)
            else:
                failed.append(pkg)

        restore_script: Optional[Path] = None
        if not dry_run and successful:
            removed_log = self.dumps_dir / "removed_packages.txt"
            removed_log.write_text("\n".join(successful) + "\n", encoding="utf-8")
            restore_script = self.generate_restore_script(successful)

        post_mem = None
        if not dry_run and successful:
            self.wait_for_system_stabilization(
                delay_seconds=settle_delay,
                interactive_confirm=wait_confirmation,
            )
            post_mem = self.get_memory_snapshot()
        else:
            post_mem = initial_mem

        self.display_optimization_report(
            initial_mem=initial_mem,
            post_mem=post_mem,
            removed_packages_count=len(successful),
            mode_label=mode.value,
            dry_run=dry_run,
        )

        return DebloatSummary(
            mode=mode,
            dry_run=dry_run,
            total_targeted=len(targets),
            successful=successful,
            failed=failed,
            restore_script_path=restore_script,
            initial_memory=initial_mem,
            post_memory=post_mem,
        )

    # =========================================================================
    # Smart Rollback: Reinstall Bloatware Engine
    # =========================================================================

    def reinstall_package(self, package_name: str) -> bool:
        """Reinstalls a previously uninstalled system package for user 0.

        Uses: adb shell pm install-existing --user 0 <package_name>

        Args:
            package_name: Android package identifier.

        Returns:
            True if installation succeeded, False otherwise.
        """
        command_args = ["shell", "pm", "install-existing", "--user", "0", package_name]
        result = self._run_adb(command_args)
        out = result.stdout.strip()

        if "installed for user" in out.lower() or "Success" in out:
            print(f"  [✓] Restored: {package_name}")
            return True

        err = result.stderr.strip() or out
        print(f"  [✗] Failed to restore {package_name}: {err}")
        return False

    def reinstall_profile_bloatware(
        self, profile_path: Optional[Path] = None
    ) -> Optional[RestoreSummary]:
        """Smart Rollback: Reinstalls missing profile bloatware back to the device.

        Live Check Logic:
        1. Queries real-time installed packages on the phone.
        2. Compares against packages defined in the active profile (safe + all advanced subcategories).
        3. If a package is already installed, skips it cleanly without issuing redundant commands.
        4. If a package is missing, executes `adb shell pm install-existing --user 0 <pkg>`.

        Args:
            profile_path: Optional path to profile JSON.

        Returns:
            RestoreSummary containing counts of skipped, restored, and failed packages.
        """
        resolved_path = profile_path or self.resolve_profile_path()
        if not resolved_path:
            return None

        profile_data = self.load_profile(resolved_path)
        if not profile_data:
            return None

        print("\n" + "=" * 65)
        print("  SMART ROLLBACK: REINSTALL PROFILE BLOATWARE")
        print(f"  Profile: {profile_data.get('profile_name', resolved_path.name)}")
        print("=" * 65)

        live_packages = self.fetch_live_packages()
        if not live_packages:
            print("[-] Rollback cancelled: Unable to retrieve live packages from device.")
            return None

        categories = profile_data.get("categories", {})
        safe_pkgs = categories.get("safe_to_remove", {}).get("packages", [])

        advanced_pkgs: List[str] = []
        adv_data = categories.get("advanced_remove", {})
        if "sub_categories" in adv_data:
            for sub in adv_data["sub_categories"].values():
                advanced_pkgs.extend(sub.get("packages", []))
        elif "packages" in adv_data:
            advanced_pkgs.extend(adv_data["packages"])

        all_profile_bloatware = sorted(list(set(safe_pkgs + advanced_pkgs)))

        already_present: List[str] = []
        missing_to_restore: List[str] = []

        for pkg in all_profile_bloatware:
            if pkg in live_packages:
                already_present.append(pkg)
            else:
                missing_to_restore.append(pkg)

        print(f"[*] Total Bloatware Rules in Profile : {len(all_profile_bloatware)}")
        print(f"[+] Already Present on Phone (Skip)  : {len(already_present)}")
        print(f"[!] Missing on Phone (To Reinstall)  : {len(missing_to_restore)}")
        print("-" * 65)

        if not missing_to_restore:
            print("[✓] All profile packages are already present on your phone. Nothing to restore!")
            print("=" * 65 + "\n")
            return RestoreSummary(
                total_profile_packages=len(all_profile_bloatware),
                already_installed=already_present,
                successfully_restored=[],
                failed_to_restore=[],
            )

        restored_list: List[str] = []
        failed_list: List[str] = []

        for index, pkg in enumerate(missing_to_restore, start=1):
            prefix = f"[{index}/{len(missing_to_restore)}]"
            print(f"{prefix} Restoring missing package: {pkg}...")
            if self.reinstall_package(pkg):
                restored_list.append(pkg)
            else:
                failed_list.append(pkg)

        print("\n" + "=" * 65)
        print("  ROLLBACK EXECUTION SUMMARY")
        print("=" * 65)
        print(f"[*] Total Profile Targets   : {len(all_profile_bloatware)}")
        print(f"[*] Skipped (Already Live)  : {len(already_present)}")
        print(f"[+] Successfully Restored   : {len(restored_list)}")
        print(f"[-] Failed / Unavailable    : {len(failed_list)}")
        print("=" * 65 + "\n")

        return RestoreSummary(
            total_profile_packages=len(all_profile_bloatware),
            already_installed=already_present,
            successfully_restored=restored_list,
            failed_to_restore=failed_list,
        )

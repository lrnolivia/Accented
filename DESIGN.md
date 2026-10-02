# Accented visual truth

Mode: Operate. Platform: GTK 4 and libadwaita on GNOME.
Reference: GameBridge Lite at 3606f651319891a094a1e80625ac36591be79f4c.

The primary window is intentionally quiet. Preserve the centered icon/title introduction,
one main card, system typography, native header bar, native color dialog, native buttons,
focus states, light/dark appearance and high-contrast behavior.

Primary path:
1. See/edit the current hex and swatch.
2. Choose a color or pick a pixel from the screen.
3. Optionally reopen collapsed Recent colors.
4. Apply Accent.

Secondary settings do not compete with that path. Use the native header-bar hamburger menu
for Match GNOME Desktop, Restore Original Accent, Automatically Update, Check for Updates,
What Changes, and About. Do not add a custom sidebar, toolbar, segmented control or dashboard.

Spacing remains intentionally tiered:
- Outer left/right and bottom margins: 32 logical pixels.
- Content top beneath the native header: 12 logical pixels.
- Hero internal spacing: 6 logical pixels; icon: 64 logical pixels.
- Hero to main panel: 24 logical pixels.
- Main panel interior padding: 24 logical pixels; group gaps: 16.
- Related picker actions: 12 logical pixels; label to field: 6.

The content is clamped to a readable width and vertically scrollable. Picker actions wrap
into one column in a narrow window. System text scaling is preserved; no fixed body font sizes.

Brand expression is limited to the supplied icon, centered hero composition, measured spacing,
and user color swatches. No gradients, glass, custom titlebar controls, decorative pill rails,
fake preview controls, or website/dashboard restyling.

The swatch itself is the preview. Suggested-action colors and native focus outlines remain
Adwaita-owned. Recent colors are user data, not theme chrome.

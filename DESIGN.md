# Accented visual truth

Mode: Operate. Platform: GTK 4 and libadwaita on GNOME.
Reference: GameBridge Lite at 3606f651319891a094a1e80625ac36591be79f4c.

Preserve the centered icon/title introduction and a single main panel. Use the
system font, native header bar, native color dialog, native buttons, checks,
focus states, cards, light/dark appearance and high-contrast behavior.

Spacing is intentionally tiered, not one uniform gap:
- Outer left/right and bottom margins: 32 logical pixels.
- Content top beneath the native header: 12 logical pixels.
- Hero internal spacing: 6 logical pixels; icon: 64 logical pixels.
- Hero to main panel: 24 logical pixels, independent of internal row spacing.
- Main panel interior padding: 24 logical pixels; group gaps: 16.
- Related actions: 12 logical pixels; label to field: 6.
- Main panel to scope options and actions: 20 logical pixels.

The content is clamped to a readable width and vertically scrollable. Related
picker actions wrap into a single column in a narrow window. Long option and
status labels wrap. System text scaling is preserved; no fixed body font sizes.

Brand expression is limited to the supplied icon, centered hero composition,
measured spacing, and color swatches. Accent preview recolors only native sample
controls. No gradients, glass, custom titlebar controls, decorative pill rails,
or generic website/dashboard restyling.

Suggested action colors and native focus outlines remain Adwaita-owned outside
the explicit preview. Swatches are genuine user color data, not theme chrome.

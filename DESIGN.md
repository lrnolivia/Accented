# Accented visual truth

Mode: Operate. Platform: GTK 4 and libadwaita on GNOME.
Reference: GameBridge Lite at 3606f651319891a094a1e80625ac36591be79f4c.

The primary window is intentionally quiet. Preserve the centered icon/title introduction
and one main panel with native system typography and controls.

Primary path:
1. See/edit the current hex and swatch.
2. Choose a color or pick a pixel.
3. Optionally open collapsed Recent colors.
4. Apply Accent.

Secondary functions live in the native header-bar hamburger: Match GNOME Desktop,
Restore Original Accent, Check for Updates, What Changes, and About.

Spacing stays tiered:
- Outer left/right and bottom: 32 logical pixels.
- Content top beneath native header: 12.
- Hero internal spacing: 6; icon: 64.
- Hero to main panel: 24.
- Main panel interior padding: 24; group gaps: 16.
- Related picker actions: 12; label to field: 6.

The swatch itself is the preview. No fake sample controls, gradients, glass, custom
titlebar controls, decorative pill rails, or website/dashboard restyling.

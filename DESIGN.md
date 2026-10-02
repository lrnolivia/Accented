# Accented visual truth

Mode: Operate. Platform: GTK 4 and libadwaita on GNOME.
Reference: GameBridge Lite at 3606f651319891a094a1e80625ac36591be79f4c.

The primary window is intentionally quiet. Preserve the centered icon/title introduction
and a full-width lower control surface with native system typography and controls. The user-provided GameBridge screenshot is the chrome reference: header and hero share the darker surface; controls sit on the lighter lower surface.

Primary path:
1. See/edit the current hex and swatch.
2. Choose a color or pick a pixel.
3. Optionally open collapsed Recent colors.
4. Apply Accent.

Secondary functions live in the native header-bar hamburger: Match GNOME Desktop,
Restore Original Accent, Check for Updates, What Changes, and About.

Spacing is symmetric within each region:
- Hero padding: 24 logical pixels on every edge.
- Control-region padding: 24 logical pixels on every edge.
- Hero internal spacing: 20; icon: 96.
- Related controls retain their native grouping and 16px gaps.
- Header is flat and shares the hero surface, without a separator line.
- Resolve the bundled app icon in both source and installed launches.

The swatch itself is the preview. No fake sample controls, gradients, glass, custom
titlebar controls, decorative pill rails, or website/dashboard restyling.

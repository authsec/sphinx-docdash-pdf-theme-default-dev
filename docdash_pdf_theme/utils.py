import re
from sphinx.util import logging

logger = logging.getLogger(__name__)

def get_safe_filename(name: str) -> str:
    """Creates a filesystem-safe string from a project name."""
    safe = re.sub(r'[^A-Za-z0-9\s]+', '', name).strip().replace(' ', '_')
    return safe.lower() or "document"

def adjust_hex_brightness(hex_color: str, percentage: float) -> str:
    """
    Adjusts the brightness of a hex color.
    
    :param hex_color: The original hex color string (e.g., '#ADAEDD' or '#ADAEDD80').
    :param percentage: Float from -100.0 to 100.0. Positive values lighten, negative values darken.
    :return: A new hex color string, preserving alpha if present (e.g., '#CBE1FF' or '#CBE1FF80').
    """
    if not hex_color:
        return None
        
    hex_color = hex_color.lstrip('#')
    has_alpha = False
    alpha_str = ""
    
    # Support 4-char shorthand (RGBA)
    if len(hex_color) == 4:
        hex_color = ''.join([c*2 for c in hex_color])
        
    # Support 3-char shorthand (RGB)
    elif len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])

    # Extract and preserve alpha channel
    if len(hex_color) == 8:
        has_alpha = True
        alpha_str = hex_color[6:8]
        hex_color = hex_color[:6]
        
    if len(hex_color) != 6:
        logger.warning(f"[DocDash] Invalid hex color '#{hex_color}'. Cannot adjust brightness.")
        return f"#{hex_color}{alpha_str}"

    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    factor = percentage / 100.0

    if factor > 0:
        # Lighten towards white
        r = r + (255 - r) * factor
        g = g + (255 - g) * factor
        b = b + (255 - b) * factor
    elif factor < 0:
        # Darken towards black
        r = r * (1 + factor)
        g = g * (1 + factor)
        b = b * (1 + factor)

    # Clamp the values between 0 and 255 and format back to Hex
    r = max(0, min(255, int(round(r))))
    g = max(0, min(255, int(round(g))))
    b = max(0, min(255, int(round(b))))

    if has_alpha:
        return f"#{r:02X}{g:02X}{b:02X}{alpha_str}"
    return f"#{r:02X}{g:02X}{b:02X}"


def _hex_to_rgb(hex_color: str):
    """Helper to safely extract 8-bit RGB values from a hex string."""
    clean = hex_color.lstrip('#')
    if len(clean) == 8:
        clean = clean[:6]
    elif len(clean) == 4:
        clean = ''.join([c*2 for c in clean[:3]])
    elif len(clean) == 3:
        clean = ''.join([c*2 for c in clean])
    if len(clean) != 6:
        return 0, 0, 0
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)

def _get_luminance(hex_color: str) -> float:
    """Calculates relative luminance according to WCAG 2.0 standards."""
    r, g, b = _hex_to_rgb(hex_color)
    srgb = [x / 255.0 for x in (r, g, b)]
    linear = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

def _get_contrast_ratio(lum1: float, lum2: float) -> float:
    """Calculates the contrast ratio between two relative luminance values."""
    l1 = max(lum1, lum2)
    l2 = min(lum1, lum2)
    return (l1 + 0.05) / (l2 + 0.05)

def get_highest_contrast_color(foreground_color: str, background_color: str, target: str = 'foreground', adjust_percent: float = 0.0) -> str:
    """
    Modifies the target color to ensure a WCAG 2.0 contrast ratio of at least 4.5:1.
    
    :param foreground_color: Hex color string (e.g., text color).
    :param background_color: Hex color string (e.g., background color).
    :param target: 'foreground' or 'background' (which color should be shifted to reach compliance).
    :param adjust_percent: Additional percentage to lighten/darken the final valid output.
    :return: A WCAG compliant hex color string, preserving alpha.
    """
    if not foreground_color or not background_color:
        return None
        
    if target == 'foreground':
        target_color = foreground_color
        fixed_color = background_color
    else:
        target_color = background_color
        fixed_color = foreground_color
        
    lum_fixed = _get_luminance(fixed_color)
    lum_target = _get_luminance(target_color)
    
    candidate = target_color
    
    if _get_contrast_ratio(lum_fixed, lum_target) < 4.5:
        # 0.17912 is the exact luminance where black and white offer identical contrast (4.58)
        direction = -1 if lum_fixed > 0.17912 else 1
        
        # Iteratively shift the target color towards black/white until it hits the 4.5 threshold
        for i in range(1, 101):
            test_color = adjust_hex_brightness(target_color, i * direction)
            if _get_contrast_ratio(lum_fixed, _get_luminance(test_color)) >= 4.5:
                candidate = test_color
                break
        else:
            # Fallback to pure black/white if loop is exhausted
            clean = target_color.lstrip('#')
            base = "#000000" if direction == -1 else "#FFFFFF"
            
            if len(clean) == 8:
                candidate = base + clean[6:8]
            elif len(clean) == 4:
                candidate = base + (clean[3]*2)
            else:
                candidate = base
                
    if adjust_percent != 0.0:
        return adjust_hex_brightness(candidate, adjust_percent)
        
    return candidate

def hex_to_cmyk_string(hex_color: str) -> str:
    """Converts a hex color string (e.g., '#FF0000') to a LaTeX CMYK string."""
    if not hex_color:
        return None
        
    hex_color = hex_color.lstrip('#')
    
    # Support 8-char (RGBA) by dropping alpha, and 3-char shorthand
    if len(hex_color) == 8:
        hex_color = hex_color[:6]
    elif len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
        
    if len(hex_color) != 6:
        logger.warning(f"[DocDash] Invalid hex color '#{hex_color}'. Falling back to black.")
        return "0, 0, 0, 1"

    # Convert Hex to RGB [0.0 - 1.0]
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    # Calculate CMYK
    k = 1.0 - max(r, g, b)
    if k == 1.0:
        return "0, 0, 0, 1"
    
    c = (1.0 - r - k) / (1.0 - k)
    m = (1.0 - g - k) / (1.0 - k)
    y = (1.0 - b - k) / (1.0 - k)

    return f"{c:.3f}, {m:.3f}, {y:.3f}, {k:.3f}"
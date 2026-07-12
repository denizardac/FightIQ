"""
Canonical filename helpers — single source of truth for visual asset names.

Every module that WRITES or LOOKS UP a generated visual (Card_*, Radar_*,
Versus_*, Reel_*) must use these helpers. Divergent ad-hoc sanitizers caused
media to silently go missing for names like "Casey O'Neill" or
"Kai Kara-France" (generator kept punctuation, lookup stripped it).
"""
import unicodedata


def safe_filename(name: str) -> str:
    """ASCII-fold accents, drop non-alphanumerics (keep spaces), spaces -> underscores.

    'Casey O'Neill'   -> 'Casey_ONeill'
    'Kai Kara-France' -> 'Kai_KaraFrance'
    'José Aldo'       -> 'Jose_Aldo'
    """
    if not name:
        return ""
    folded = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(c for c in folded if c.isalnum() or c == " ")
    return "_".join(cleaned.split())


def safe_filename_lower(name: str) -> str:
    """Lowercase variant (used for Reel_* video files)."""
    return safe_filename(name).lower()


def versus_basename(f1: str, f2: str) -> str:
    return f"Versus_{safe_filename(f1)}_vs_{safe_filename(f2)}.png"


def radar_basename(f1: str, f2: str) -> str:
    return f"Radar_{safe_filename(f1)}_vs_{safe_filename(f2)}.png"


def card_basename(name: str) -> str:
    return f"Card_{safe_filename(name)}.png"


def pick_basename(f1: str, f2: str) -> str:
    """AI Pick card (prediction visual) filename."""
    return f"Pick_{safe_filename(f1)}_vs_{safe_filename(f2)}.png"

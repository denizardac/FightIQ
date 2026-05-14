"""
Universal Odds Format Converter
Converts between Decimal (European) and American (US) odds formats
"""

def decimal_to_american(decimal_odds):
    """
    Convert decimal odds to American format
    
    Args:
        decimal_odds (float): Decimal odds (e.g., 1.50, 2.60)
    
    Returns:
        str: American odds (e.g., "-200", "+160")
    """
    d = float(decimal_odds)
    if d <= 1.0 or d != d:  # invalid / NaN
        return "+100"
    if d >= 2.0:
        # Underdog: (Decimal - 1) × 100
        american = int((d - 1) * 100)
        return f"+{american}"
    else:
        # Favorite: -100 / (Decimal - 1)
        denom = d - 1.0
        if denom < 1e-6:
            return "-10000"
        american = int(-100 / denom)
        return str(american)

def american_to_decimal(american_odds):
    """
    Convert American odds to decimal format
    
    Args:
        american_odds (int or str): American odds (e.g., -200, +160, "-200", "+160")
    
    Returns:
        float: Decimal odds (e.g., 1.50, 2.60)
    """
    # Handle string input
    if isinstance(american_odds, str):
        american_odds = american_odds.replace("+", "")
        american_odds = int(american_odds)
    
    if american_odds > 0:
        # Positive odds (underdog)
        return round(1 + (american_odds / 100), 2)
    else:
        # Negative odds (favorite)
        return round(1 + (100 / abs(american_odds)), 2)

def normalize_odds(value, source_format="decimal"):
    """
    Normalize odds to Universal Format (both decimal and american)
    
    Args:
        value: The odds value (float for decimal, int/str for american)
        source_format (str): "decimal" or "american"
    
    Returns:
        dict: {"decimal": float, "american": str}
    """
    if source_format == "decimal":
        decimal = round(float(value), 2)
        american = decimal_to_american(decimal)
    elif source_format == "american":
        american = str(value) if isinstance(value, int) else value
        decimal = american_to_decimal(value)
    else:
        raise ValueError(f"Invalid source_format: {source_format}")
    
    return {
        "decimal": decimal,
        "american": american
    }

# Test examples
if __name__ == "__main__":
    print("=== ODDS CONVERTER TEST ===\n")
    
    # Test decimal to american
    print("Decimal -> American:")
    print(f"  1.50 -> {decimal_to_american(1.50)}")  # Favorite
    print(f"  2.00 -> {decimal_to_american(2.00)}")  # Even
    print(f"  2.60 -> {decimal_to_american(2.60)}")  # Underdog
    print(f"  3.50 -> {decimal_to_american(3.50)}")  # Heavy underdog
    
    # Test american to decimal
    print("\nAmerican -> Decimal:")
    print(f"  -200 -> {american_to_decimal(-200)}")
    print(f"  +100 -> {american_to_decimal(+100)}")
    print(f"  +160 -> {american_to_decimal(+160)}")
    print(f"  +250 -> {american_to_decimal(+250)}")
    
    # Test normalize
    print("\nNormalize (Universal Format):")
    print(f"  1.50 (decimal) -> {normalize_odds(1.50, 'decimal')}")
    print(f"  -200 (american) -> {normalize_odds(-200, 'american')}")
    print(f"  +160 (american) -> {normalize_odds('+160', 'american')}")

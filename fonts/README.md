# FightIQ Font Installation Guide

## Required Fonts for Phase 2

### 1. Bebas Neue (Headlines & Titles)
**Download**: [Google Fonts - Bebas Neue](https://fonts.google.com/specimen/Bebas+Neue)

**Direct Download Link**:
```
https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf
```

**Installation**:
```bash
# Windows PowerShell
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf" -OutFile "fonts/BebasNeue-Regular.ttf"

# Or download manually and place in fonts/ directory
```

### 2. Roboto Bold (Body Text)
**Download**: [Google Fonts - Roboto](https://fonts.google.com/specimen/Roboto)

**Direct Download Link**:
```
https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf
```

**Installation**:
```bash
# Windows PowerShell
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf" -OutFile "fonts/Roboto-Bold.ttf"

# Or download manually and place in fonts/ directory
```

### 3. Roboto Regular (Secondary Text)
**Optional but recommended**

**Direct Download Link**:
```
https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf
```

**Installation**:
```bash
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf" -OutFile "fonts/Roboto-Regular.ttf"
```

---

## Quick Install Script

Run this in PowerShell from the FightIQ directory:

```powershell
# Create fonts directory (if it doesn't exist)
if (!(Test-Path fonts)) { mkdir fonts }

# Download fonts
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf" -OutFile "fonts/BebasNeue-Regular.ttf"
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf" -OutFile "fonts/Roboto-Bold.ttf"
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf" -OutFile "fonts/Roboto-Regular.ttf"

Write-Host "✅ Fonts downloaded successfully!" -ForegroundColor Green
```

---

## Verification

After installation, your `fonts/` directory should contain:
```
fonts/
├── BebasNeue-Regular.ttf      (Headlines)
├── Roboto-Bold.ttf            (Body Bold)
└── Roboto-Regular.ttf         (Body Regular)
```

---

## Fallback Strategy

The visual engine (`06_visual_engine.py`) includes fallback logic:
1. Try custom fonts in `fonts/` directory
2. Fall back to Windows system fonts (`C:/Windows/Fonts/arial.ttf`)
3. Ultimate fallback to PIL default font

**No crashes if fonts are missing** - system will use available alternatives.

---

## Testing

After installation, test font loading:
```bash
python -c "from PIL import ImageFont; font = ImageFont.truetype('fonts/BebasNeue-Regular.ttf', 36); print('✅ Fonts loaded successfully')"
```

If successful, you're ready for the visual overhaul!

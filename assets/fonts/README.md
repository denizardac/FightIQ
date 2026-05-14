# FightIQ Font Installation Guide

Fonts live in `assets/fonts/` (this directory). They are already present in the repository.
If they are missing (e.g. after a fresh clone), follow the instructions below.

---

## Required Fonts

### 1. Bebas Neue (Headlines & Titles)
**Download**: [Google Fonts - Bebas Neue](https://fonts.google.com/specimen/Bebas+Neue)

**Direct Download Link**:
```
https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf
```

**Installation**:
```powershell
# Run from FightIQ project root
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf" -OutFile "assets/fonts/BebasNeue-Regular.ttf"
```

### 2. Roboto Bold (Body Text)
**Download**: [Google Fonts - Roboto](https://fonts.google.com/specimen/Roboto)

**Direct Download Link**:
```
https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf
```

**Installation**:
```powershell
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf" -OutFile "assets/fonts/Roboto-Bold.ttf"
```

### 3. Roboto Regular (Secondary Text)
**Optional but recommended**

**Direct Download Link**:
```
https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf
```

**Installation**:
```powershell
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf" -OutFile "assets/fonts/Roboto-Regular.ttf"
```

---

## Quick Install (All 3 Fonts)

Run from FightIQ project root in PowerShell:

```powershell
# Create directory if it doesn't exist
if (!(Test-Path "assets/fonts")) { mkdir "assets/fonts" }

Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf" -OutFile "assets/fonts/BebasNeue-Regular.ttf"
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf" -OutFile "assets/fonts/Roboto-Bold.ttf"
Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf" -OutFile "assets/fonts/Roboto-Regular.ttf"

Write-Host "✅ Fonts downloaded successfully!" -ForegroundColor Green
```

---

## Expected Layout

```
assets/fonts/
├── BebasNeue-Regular.ttf      (Headlines)
├── Roboto-Bold.ttf            (Body Bold)
└── Roboto-Regular.ttf         (Body Regular)
```

---

## Fallback Strategy

The visual engines include automatic fallbacks:
1. Try custom fonts in `assets/fonts/` (configured in `core/config.py`)
2. Fall back to Windows system fonts (`arial.ttf`)
3. Ultimate fallback to PIL default font

**No crashes if fonts are missing** — system will use available alternatives, but visual quality will be degraded.

---

## Verification

After installation, test font loading:
```bash
python -c "from PIL import ImageFont; font = ImageFont.truetype('assets/fonts/BebasNeue-Regular.ttf', 36); print('✅ Fonts loaded successfully')"
```

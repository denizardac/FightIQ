# 🎨 MANUAL BACKGROUND CREATION FOR BETTING TICKETS

## Sorun
Imagen API, `google.generativeai` paketinde artık desteklenmiyor.
Yeni `google.genai` paketine geçiş gerekiyor VEYA Vertex AI kullanılması gerekiyor.

## Geçici Çözüm: Manuel Arka Plan Oluşturma

### Yöntem 1: Kod ile Gradient Pattern (ÜCRETSİZ)
Ticketlar şu an bu yöntemi kullanıyor - gradient + noise texture.
✅ Zaten çalışıyor, hiç maliyet yok.

### Yöntem 2: Stock Fotoğraf Kullan (ÜCRETSİZ)
1. Aşağıdaki sitelerden ücretsiz MMA/UFC temalı görsel indir:
   - Pexels.com
   - Unsplash.com
   - Pixabay.com

2. Arama terimleri:
   - "mma octagon dark"
   - "boxing ring neon"
   - "abstract sports" + "red" / "green" / "blue"

3. Görselleri şu boyutlara getir: 1080x1350px (vertical)

4. Kaydet:
   ```
   assets/ticket_backgrounds/safe_bg.png
   assets/ticket_backgrounds/violence_bg.png
   assets/ticket_backgrounds/value_bg.png
   ```

### Yöntem 3: Canva ile Oluştur (ÜCRETSİZ)
1. Canva.com'a git
2. Custom size: 1080x1350px
3. Templates > Sports > Dark theme ile başla
4. Background gradient uygula (yeşil/kırmızı/mavi)
5. Noise texture veya pattern ekle
6. Export PNG

### Yöntem 4: Vertex AI Imagen (ÜCRETLI - $0.02-0.04/görsel)
Daha karmaşık setup gerektiriyor:

1. Google Cloud Console'da Vertex AI etkinleştir
2. `google-cloud-aiplatform` paketini kur:
   ```bash
   pip install google-cloud-aiplatform
   ```

3. Authentication setup yap
4. Kod örneği (farklı API):
   ```python
   from vertexai.preview.vision_models import ImageGenerationModel
   
   model = ImageGenerationModel.from_pretrained("imagegeneration@006")
   response = model.generate_images(
       prompt="dark sports betting background",
       number_of_images=1
   )
   ```

## ÖNERİ
**Yöntem 1** ile devam et. Kod-generated gradient backgrounds çok düzgün gözüküyor!

Eğer gerçekten AI-generated backgrounds istiyorsan:
1. VEYA Canva Pro kullan (AI background generator var)
2. VEYA Midjourney / DALL-E 3 kullan (daha ucuz ve kolay)
3. VEYA Vertex AI setup yap (karmaşık)

## Şu Anki Durum
✅ Ticketlar çalışıyor
✅ Gradients güzel
✅ Typography premium (Roboto Bold + Bebas Neue)
✅ Dövüşçü fotoğrafları entegre (ImageHunter)
⚠️ AI backgrounds geçici olarak kapalı (fallback aktif)

SONUÇ: Sistemin %95'i hazır ve production-ready!

"""Imagen image generation with model fallbacks (Gemini Developer API ids change often)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def imagen_model_candidates():
    import core.config as cfg

    primary = getattr(cfg, "IMAGEN_MODEL", None) or "imagen-3.0-generate-002"
    rest = list(getattr(cfg, "IMAGEN_MODEL_FALLBACKS", []) or [])
    seen = set()
    out = []
    for m in [primary] + rest:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def generate_imagen_image(client, prompt, config_obj):
    """
    Try each configured model until one succeeds.
    Returns PIL.Image in RGB mode, or None.
    """
    if client is None:
        return None
    from google.genai import types as genai_types
    from PIL import Image
    import io

    last_err = None
    for model_id in imagen_model_candidates():
        try:
            resp = client.models.generate_images(
                model=model_id,
                prompt=prompt,
                config=config_obj
                if config_obj is not None
                else genai_types.GenerateImagesConfig(number_of_images=1),
            )
            if resp.generated_images:
                raw = resp.generated_images[0].image.image_bytes
                return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            last_err = e
            log.debug("Imagen model %s failed: %s", model_id, e)
            continue
    if last_err:
        log.warning("All Imagen candidates failed: %s", last_err)
    return None

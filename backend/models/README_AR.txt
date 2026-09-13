ضع نموذج Whisper هنا لكي يجده التطبيق فوراً (بدون إنترنت).

الشكل المطلوب — مجلد فيه ملف model.bin:

  backend/models/faster-whisper-large-v3/
        ├── model.bin            (الأكبر، ~3 جيجا)
        ├── config.json
        ├── tokenizer.json
        ├── vocabulary.txt
        └── preprocessor_config.json

أو النموذج الأخف:
  backend/models/faster-whisper-medium/   (نفس الملفات، ~1.5 جيجا)

أسهل طريقة (إنترنت): من مجلد المشروع شغّل:
      python scripts/fetch_models.py            (يحمّل large-v3)
      python scripts/fetch_models.py medium     (الأخف)

للتأكد أن التطبيق يراه:
      python scripts/check_models.py

تفاصيل كاملة والطريقة اليدوية: راجع ملف MODELS_AR.md في جذر المشروع.

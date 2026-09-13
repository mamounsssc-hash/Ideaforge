# 🎙️ دليل نماذج Whisper (بالعربي) — تحميلها ووضعها والكشف التلقائي

> Whisper هو النموذج الذي يحوّل صوت الفيديو إلى نص بتوقيت دقيق لكل كلمة (أساس الكابشن والقص). التطبيق يدعم نموذجين فقط:
> - **large-v3** — الأدق (الافتراضي)، حجمه **~3 جيجا**.
> - **medium** — أخف وأسرع، حجمه **~1.5 جيجا** (اختره لو جهازك ضعيف أو المساحة قليلة).

**الجديد في هذا التحديث:** التطبيق الآن **يكتشف أي نموذج موجود تلقائياً ويشغّله فوراً بدون إنترنت**، وصار تحميله من الخارج سهلاً جداً، وإن لم يجده يعطيك رسالة واضحة تخبرك ماذا تفعل.

---

## 📍 أين يبحث التطبيق عن النموذج؟ (بالترتيب)

عند أول عملية تفريغ صوتي، يبحث التطبيق بهذا الترتيب ويستخدم أول ما يجده:

1. **مسار خارجي صريح** — لو ضبطت `IDEAFORGE_WHISPER_MODEL_DIR` في ملف `backend/.env` على مجلد فيه `model.bin`.
2. **مجلد المشروع** — `backend/models/` (وهذا الأسهل والموصى به). يقبل هذه الأسماء:
   - `backend/models/faster-whisper-large-v3/`
   - `backend/models/large-v3/`
   - أو حتى مجلد كاش HuggingFace منسوخ (`models--Systran--faster-whisper-large-v3/snapshots/…`).
3. **كاش النظام** — كاش HuggingFace المعتاد (إن كنت حمّلته سابقاً على الجهاز).
4. **التحميل التلقائي** — لو لا شيء موجود ومعك إنترنت، يحمّله مرة واحدة تلقائياً عند أول استخدام.

> **الشرط الوحيد ليُعتبر المجلد نموذجاً صالحاً:** أن يحتوي على ملف **`model.bin`**.

---

## 🖱️ الأسهل على الإطلاق — ملف تضغط عليه ضغطتين (معك إنترنت)

1. افتح مجلد المشروع `Ideaforge`.
2. **ويندوز:** اضغط ضغطتين على ملف **`GET_MODEL.bat`**. · **ماك:** اضغط ضغطتين على **`GET_MODEL.command`**.
3. ستفتح نافذة سوداء تسألك: اكتب **`1`** ثم Enter لتحميل الأفضل (large-v3)، أو **`2`** ثم Enter للأخف (medium). (أو فقط اضغط Enter وسيأخذ الأفضل).
4. انتظر حتى ينتهي التحميل (large-v3 كبير ~3 جيجا، خذ وقتك). في أول مرة قد يثبّت بعض الأشياء تلقائياً.
5. في النهاية لو رأيت كلمة **`[FOUND]`** فأنت جاهز. أغلق النافذة وشغّل التطبيق عادي بـ `START.bat`.

> هذا الملف يجهّز كل شيء بنفسه (البيئة + الأدوات) ثم يحمّل النموذج ويضعه في المكان الصحيح. لا تحتاج تكتب أي أوامر.

---

## ✅ الطريقة 1 — أمر واحد (معك إنترنت على نفس الجهاز)

من مجلد المشروع، وبعد تفعيل البيئة (`.venv`)، شغّل أمراً واحداً:

```bash
# ويندوز:
.\.venv\Scripts\python.exe scripts\fetch_models.py

# ماك / لينكس:
python scripts/fetch_models.py
```

- هذا يحمّل **large-v3** ويضعه في `backend/models/faster-whisper-large-v3/`.
- للنموذج الأخف: `python scripts/fetch_models.py medium`
- للاثنين معاً: `python scripts/fetch_models.py large-v3 medium`
- **لو النموذج موجود أصلاً، يتخطّاه ولا يعيد التحميل.**

ثم تأكّد أن التطبيق يراه:
```bash
python scripts/check_models.py
```
لو ظهر `[FOUND] large-v3 -> …backend/models/faster-whisper-large-v3` فأنت جاهز. شغّل التطبيق عادي.

---

## 🖐️ الطريقة 2 — اليدوية (جهاز بلا إنترنت، أو تريد التحميل من مكان آخر)

حمّل الملفات من HuggingFace على **أي جهاز فيه إنترنت**، ثم انسخ المجلد إلى جهازك.

### الملفات المطلوبة (من مستودع النموذج على HuggingFace)
رابط النموذج:
- large-v3 → `https://huggingface.co/Systran/faster-whisper-large-v3/tree/main`
- medium → `https://huggingface.co/Systran/faster-whisper-medium/tree/main`

نزّل **كل هذه الملفات** (زر التحميل ⬇️ بجانب كل ملف):
```
model.bin              ← الأهم والأكبر (~3 جيجا للـ large-v3)
config.json
tokenizer.json
vocabulary.txt
preprocessor_config.json
```

### أين تضعها بالضبط
أنشئ هذا المجلد وضع الملفات الخمسة **مباشرة بداخله** (لا مجلد فرعي إضافي):
```
Ideaforge/
└── backend/
    └── models/
        └── faster-whisper-large-v3/     ← أنشئ هذا المجلد
            ├── model.bin
            ├── config.json
            ├── tokenizer.json
            ├── vocabulary.txt
            └── preprocessor_config.json
```
> للنموذج الأخف استخدم اسم المجلد `faster-whisper-medium` بدلاً منه.

### تأكّد
```bash
python scripts/check_models.py
```
يجب أن يظهر `[FOUND]`. تم — التطبيق سيستخدمه فوراً وبدون إنترنت.

> **بديل سطر أوامر لليدوي (إن توفر أمر git):**
> ```bash
> pip install huggingface_hub
> huggingface-cli download Systran/faster-whisper-large-v3 --local-dir backend/models/faster-whisper-large-v3
> ```

---

## 🗂️ الطريقة 3 — نموذج موجود خارج المشروع

لو النموذج عندك في مكان آخر (قرص خارجي مثلاً) ولا تريد نسخه:
1. افتح `backend/.env` (انسخ `.env.example` إليه إن لم يوجد).
2. أضف سطراً يشير للمجلد الذي فيه `model.bin`:
```ini
IDEAFORGE_WHISPER_MODEL_DIR=D:\models\faster-whisper-large-v3
```
3. `python scripts/check_models.py` للتأكد. هذا المسار له الأولوية على كل شيء.

---

## ⚙️ اختيار النموذج الأخف (جهاز ضعيف / مساحة قليلة)

في `backend/.env` اضبط:
```ini
IDEAFORGE_WHISPER_MODEL=medium
```
ثم حمّل medium (`python scripts/fetch_models.py medium`) أو ضعه يدوياً. النموذج الافتراضي هو large-v3.

---

## 🧯 حل المشكلات

- **رسالة "Could not load the Whisper model" عند القص:** لا يوجد نموذج محلي ولا إنترنت. طبّق الطريقة 1 أو 2 (الرسالة نفسها تكتب لك الأمر والمجلد المطلوب).
- **`check_models.py` يقول `[missing]` رغم أنك نسخت الملفات:** تأكد أن `model.bin` موجود **مباشرة** داخل `backend/models/faster-whisper-large-v3/` (ليس داخل مجلد فرعي، وليس باسم مختلف).
- **التحميل بطيء/يتوقف:** large-v3 كبير (~3 جيجا). جرّب medium، أو حمّله يدوياً على شبكة أفضل وانسخه.
- **"No module named huggingface_hub":** ثبّت التبعيات أولاً: `pip install -r backend/requirements.txt`.
- **المساحة ممتلئة:** احذف النموذج الذي لا تستخدمه من `backend/models/`، واكتفِ بواحد.

---

## 🧠 كيف يعمل هذا داخلياً (للمرجع)

- `backend/app/config.py` → `find_local_whisper_model()` يبحث في المسارات أعلاه، و`resolve_whisper_model()` يعيد **مسار المجلد المحلي** إن وُجد وإلا اسم النموذج.
- `backend/app/pipeline/transcribe.py` يطبع من أين حمّل النموذج، ويعطي رسالة خطأ واضحة إن غاب.
- `scripts/fetch_models.py` يحمّل النموذج إلى `backend/models/` (ويتخطّى الموجود).
- `scripts/check_models.py` يطبع بالضبط ما "يراه" التطبيق.
- ملفات `model.bin` مستثناة من git (لا تُرفع)، فيبقى المستودع خفيفاً.

# دليل التشغيل السريع (بالعربي)

هذا الدليل يشرح تشغيل التطبيق خطوة بخطوة. لا يحتاج خبرة برمجية.

---

## مرة واحدة فقط: تجهيز الجهاز (ويندوز)

### 1) ثبّت Python
- افتح متجر Microsoft Store، ابحث عن **Python 3.11** أو أحدث، واضغط تثبيت.
- أو من الموقع: https://www.python.org/downloads/ — وأثناء التثبيت **ضع علامة على «Add Python to PATH»**.

### 2) ثبّت ffmpeg
- افتح **PowerShell** (اكتب في قائمة ابدأ: PowerShell).
- الصق هذا الأمر واضغط Enter:
```powershell
winget install Gyan.FFmpeg
```
- بعد انتهائه، **أغلق نافذة PowerShell وافتحها من جديد** (مهم).

### 3) نزّل المشروع
- إن كان عندك Git:
```powershell
git clone https://github.com/mamounsssc-hash/Ideaforge.git
cd Ideaforge
git checkout claude/professional-clipping-app-6uad5w
```
- إن لم يكن عندك Git: افتح صفحة المستودع على GitHub، بدّل الفرع إلى
  `claude/professional-clipping-app-6uad5w`، ثم **Code ← Download ZIP**، وفكّ الضغط.

---

## الطريقة (أ): التشغيل **بدون** Qwen — الأسهل والموصى به

هذه الطريقة تعمل بالكامل محلياً ومجاناً، وتختار اللقطات بذكاء داخلي بدون أي موديل.

1) افتح PowerShell **داخل مجلد المشروع** (Ideaforge).
2) التجهيز (مرة واحدة). هذا الأمر ينشئ البيئة ويثبّت المكتبات **وينزّل نموذجَي الصوت** (كبيران، قد يأخذ وقتاً ومساحة):
```powershell
.\scripts\setup.ps1
```
3) التشغيل (كل مرة تريد استخدام التطبيق):
```powershell
.\scripts\run.ps1
```
4) سيفتح المتصفح تلقائياً على العنوان: **http://127.0.0.1:8000**
   - إن لم يفتح، افتح المتصفح واكتب العنوان بنفسك.
5) داخل الصفحة: ارفع فيديو أو الصق رابطاً، اضغط **Find clips**، اختر ستايل الكابشن،
   ثم **Render** لأي لقطة. للإيقاف: أغلق نافذة PowerShell.

**هذا كل شيء.** لا تحتاج أي إعداد آخر.

---

## الطريقة (ب): التشغيل **مع** Qwen — لاختيار أذكى (اختياري)

Qwen يضيف ترتيباً أذكى للّقطات وعناوين أفضل. التطبيق يعمل بدونه، لكن هذه طريقة ربطه.

### الخطوة 1: شغّل Qwen كخادم محلي
أسهل طريقة هي برنامج بواجهة رسومية يعطيك «خادماً» بعنوان مثل `http://localhost:PORT/v1`:

- **LM Studio** (الأسهل): حمّله من https://lmstudio.ai ← نزّل موديل Qwen ← افتح تبويب
  **Local Server** ← اضغط **Start**. سيظهر لك عنوان مثل `http://localhost:1234/v1`
  واسم الموديل.
- **أو Ollama**: من https://ollama.com ← بعد التثبيت شغّل في PowerShell مثلاً:
  ```powershell
  ollama pull qwen2.5vl
  ```
  والعنوان سيكون `http://localhost:11434/v1`.

### الخطوة 2: أخبر التطبيق بالعنوان
1) في مجلد المشروع، انسخ الملف `.env.example` وسمّه `.env` وضعه داخل مجلد `backend`.
   (أي: المسار يصبح `backend\.env`).
2) افتحه بالمفكرة (Notepad) واضبط هذه السطور:
```ini
IDEAFORGE_LLM_ENABLED=true
IDEAFORGE_LLM_BASE_URL=http://localhost:1234/v1
IDEAFORGE_LLM_MODEL=اسم-الموديل-كما-يظهر-في-برنامجك
IDEAFORGE_LLM_VISION=true
```
- **BASE_URL**: ضع العنوان الذي أعطاك إياه برنامجك (LM Studio غالباً `...:1234/v1`،
  Ollama `...:11434/v1`).
- **MODEL**: اكتب اسم الموديل كما يظهر عندك (مثل `qwen2.5vl` أو ما يعرضه LM Studio).
- **VISION=true**: اتركها true إذا كان الموديل **Qwen3-VL** (يرى الصور). إن كان موديلاً
  نصياً فقط اجعلها `false`.

### الخطوة 3: شغّل التطبيق كالمعتاد
```powershell
.\scripts\run.ps1
```
الآن سيستخدم التطبيق Qwen تلقائياً. **إن توقّف Qwen أو أغلقته، لا مشكلة** — التطبيق
يرجع وحده للاختيار الداخلي ولا يتوقف.

لإيقاف استخدام Qwen لاحقاً: غيّر `IDEAFORGE_LLM_ENABLED=false` في نفس الملف.

---

## ملاحظات سريعة

- **نماذج Whisper (التفريغ الصوتي):** التطبيق يكتشف أي نموذج تضعه في `backend/models/`
  ويشغّله فوراً بلا إنترنت. لتحميله بسهولة: `python scripts/fetch_models.py` — وللتأكد أنه
  يراه: `python scripts/check_models.py`. الدليل الكامل (وطريقة يدوية بلا إنترنت) في **`MODELS_AR.md`**.
- **الجهاز ضعيف / مساحة قليلة؟** أضف هذا السطر في `backend\.env` لاستخدام النموذج الأخف:
  ```ini
  IDEAFORGE_WHISPER_MODEL=medium
  ```
- **وضع «Create» (فيديو بلا وجه):** يحتاج إنترنت لصوت التعليق (edge-tts مجاني). أما وضع
  «Clip» فيعمل بلا إنترنت بعد التجهيز.
- **ماك / لينكس:** نفس الفكرة لكن استخدم:
  ```bash
  ./scripts/setup.sh
  ./scripts/run.sh
  ```
  وثبّت ffmpeg بـ `brew install ffmpeg` (ماك) أو `sudo apt install ffmpeg` (لينكس).
- **إن ظهر خطأ ffmpeg:** أغلق PowerShell وافتحه من جديد بعد تثبيت ffmpeg.

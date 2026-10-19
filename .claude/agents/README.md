# وكلاء المشروع (Sub-agents)

ملفات هذا المجلد وكلاء فرعيون لـ Claude Code، مختارون لما يحتاجه هذا المشروع
(واجهة عربية RTL بملف واحد، على Supabase + Chart.js).

| الوكيل | متى تستدعيه |
|---|---|
| `security-ai-generated-code-auditor` | فحص أمني: RLS في Supabase، مفاتيح مكشوفة، تحقق من الصلاحيات |
| `engineering-minimal-change-engineer` | تعديل محدود النطاق داخل `index.html` الضخم |
| `engineering-i18n-engineer` | مشاكل RTL/bidi، تنسيق التواريخ والأرقام بالعربية |
| `engineering-database-optimizer` | تصميم مخطط Postgres/Supabase والفهارس |
| `engineering-data-visualization-engineer` | لوحات ورسوم Chart.js |
| `engineering-code-reviewer` | مراجعة عامة للكود |
| `testing-accessibility-auditor` | تدقيق WCAG للنماذج والواجهة |

## المصدر والترخيص

مأخوذة من [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)
برخصة MIT — Copyright (c) 2025 AgentLand Contributors.

التعديل الوحيد المطبّق: توحيد حقل `name` في الترويسة ليطابق اسم الملف، لأن
Claude Code يتوقع معرّفًا بحروف صغيرة وشرطات لا اسم عرض فيه مسافات.

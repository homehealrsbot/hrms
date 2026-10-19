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

## وكلاء التسويق

| الوكيل | متى تستدعيه |
|---|---|
| `marketing-seo-specialist` | تدقيق SEO تقني، منع تنافس الصفحات، بنية الروابط |
| `marketing-email-strategist` | تسلسلات بريدية، تقسيم الجمهور، deliverability |
| `marketing-linkedin-content-creator` | محتوى B2B وقيادة فكرية على لينكدإن |
| `marketing-ai-citation-strategist` | الظهور في إجابات ChatGPT/Claude/Perplexity |

> ⚠️ وكلاء التسويق الأصليون لا يحتويون أي سياق سعودي أو خليجي أو عربي،
> ولا يذكرون سناب شات إطلاقًا. زوّدهم بالسياق المحلي عند الاستدعاء.

## وكيل مكتوب لنا (ليس من الحزمة)

| الوكيل | متى تستدعيه |
|---|---|
| `marketing-google-saudi` | Google Ads والكلمات العربية، Search Console و GA4، و Google Business Profile — بسياق سعودي وقواعد حماية بيانات صارمة |

هذا الوكيل **مكتوب لهذا المشروع**، لا مأخوذ من المستودع الأصلي. يغطي ما
تفتقده الحزمة: الكلمات الامتثالية (قوى، مدد، التأمينات، نطاقات)، الموسمية
الهجرية ورمضان، تفاصيل الإعلان العربي في RTL، ودورة شراء B2B الطويلة.

رأسه قواعد حماية بيانات غير قابلة للتجاوز: لا تخرج أي بيانات شخصية من
البيئة المحلية، وكل مخرجاته ملفات داخل المستودع، وأي نقل للخارج يحتاج
موافقة صريحة في كل مرة.

## المصدر والترخيص

مأخوذة من [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)
برخصة MIT — Copyright (c) 2025 AgentLand Contributors.

التعديل الوحيد المطبّق: توحيد حقل `name` في الترويسة ليطابق اسم الملف، لأن
Claude Code يتوقع معرّفًا بحروف صغيرة وشرطات لا اسم عرض فيه مسافات.

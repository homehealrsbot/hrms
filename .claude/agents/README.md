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

## وكلاء التسويق (23 من الحزمة)

مثبّتون كاملين عدا 14 وكيلًا خاصًا بالمنصات الصينية (Douyin، Xiaohongshu،
Weibo، Zhihu، Bilibili، Kuaishou، WeChat، Baidu، Taobao) — تُركت عمدًا.

**كلهم مقفلون بلا `Bash`**: `Read, Write, Edit, WebSearch, WebFetch` فقط.

البحث والقياس · `seo-specialist` `aeo-foundations` `ai-citation-strategist`
`agentic-search-optimizer` `app-store-optimizer`
القنوات · `email-strategist` `linkedin-content-creator` `tiktok-strategist`
`instagram-curator` `twitter-engager` `reddit-community-builder`
`social-media-strategist` `video-optimization-specialist`
النمو والاتصال · `growth-hacker` `content-creator` `pr-communications-manager`
`developer-community-builder` `x-twitter-intelligence-analyst`
محتوى طويل وتجارة · `book-co-author` `global-podcast-strategist`
`short-video-editing-coach` `carousel-growth-engine` `cross-border-ecommerce`

> ⚠️ ولا واحد منهم يحوي سياقًا سعوديًا أو خليجيًا أو عربيًا، ولا يُذكر
> سناب شات في أي منهم. زوّدهم بالسياق المحلي عند الاستدعاء، أو استخدم
> `marketing-google-saudi` أدناه.

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

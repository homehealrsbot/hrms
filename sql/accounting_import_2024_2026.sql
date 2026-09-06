-- ============================================================
-- ترحيل بيانات النظام المحاسبي (ERP) إلى دفتر الأستاذ العام — Home Healers HRMS
-- المصدر: ملف "نظام هوم هيلرز المحاسبي المتكامل (ERP)"
-- الجداول: gl_accounts / gl_journals / gl_journal_lines
--
-- طريقة التشغيل: Supabase ➜ SQL Editor ➜ الصق الملف كاملاً ➜ Run
-- السكربت آمن للتكرار (idempotent): لا يكرّر حساباً موجوداً ولا قيداً سبق ترحيله.
-- ============================================================

BEGIN;

-- ---------- 1) دليل الحسابات (37 حساباً) ----------
INSERT INTO gl_accounts (code, name, type, normal_side, is_contra, is_cogs)
SELECT v.code, v.name, v.type, v.normal_side, v.is_contra, v.is_cogs
FROM (VALUES
  (101, 'نقدية بالبنوك', 'Asset', 'Dr', FALSE, FALSE),   -- أصول
  (103, 'عملاء ومستحقات بوابات الدفع', 'Asset', 'Dr', FALSE, FALSE),   -- أصول
  (104, 'عهد مدينة للموظفين', 'Asset', 'Dr', FALSE, FALSE),   -- أصول
  (105, 'ضريبة القيمة المضافة (مدين)', 'Asset', 'Dr', FALSE, FALSE),   -- أصول
  (110, 'أصول ثابتة (سيارات ومعدات)', 'Asset', 'Dr', FALSE, FALSE),   -- أصول
  (111, 'مجمع إهلاك سيارات', 'Asset', 'Cr', TRUE, FALSE),   -- أصول
  (112, 'أصول غير ملموسة (تطبيق)', 'Asset', 'Dr', FALSE, FALSE),   -- أصول
  (113, 'مشاريع تحت التنفيذ', 'Asset', 'Dr', FALSE, FALSE),   -- أصول
  (201, 'دائنون وموردون', 'Liability', 'Cr', FALSE, FALSE),   -- خصوم
  (202, 'رواتب مستحقة', 'Liability', 'Cr', FALSE, FALSE),   -- خصوم
  (203, 'إيرادات مؤجلة (بكجات)', 'Liability', 'Cr', FALSE, FALSE),   -- خصوم
  (204, 'ضريبة ق.م مستحقة', 'Liability', 'Cr', FALSE, FALSE),   -- خصوم
  (205, 'أقساط سيارات مستحقة', 'Liability', 'Cr', FALSE, FALSE),   -- خصوم
  (206, 'قروض سيارات طويل الأجل', 'Liability', 'Cr', FALSE, FALSE),   -- خصوم
  (301, 'رأس المال المستثمر', 'Equity', 'Cr', FALSE, FALSE),   -- حقوق ملكية
  (302, 'أرباح مبقاة (آلي)', 'Equity', 'Cr', FALSE, FALSE),   -- حقوق ملكية
  (303, 'جاري المالك - مسحوبات', 'Equity', 'Dr', TRUE, FALSE),   -- حقوق ملكية
  (304, 'تمويل إضافي / تسويات', 'Equity', 'Cr', FALSE, FALSE),   -- حقوق ملكية
  (401, 'إجمالي الإيرادات (عملاء)', 'Revenue', 'Cr', FALSE, FALSE),   -- إيرادات
  (402, 'إيرادات تعاقدات', 'Revenue', 'Cr', FALSE, FALSE),   -- إيرادات
  (403, 'مبالغ مستردة للبنك', 'Revenue', 'Dr', TRUE, FALSE),   -- إيرادات
  (404, 'مردودات مبيعات', 'Revenue', 'Dr', TRUE, FALSE),   -- إيرادات
  (501, 'تكلفة أطباء (Part Time)', 'Expense', 'Dr', FALSE, TRUE),   -- مصروفات
  (502, 'تكلفة أطباء (Full Time)', 'Expense', 'Dr', FALSE, TRUE),   -- مصروفات
  (503, 'مصروفات تشغيلية للطاقم الطبي', 'Expense', 'Dr', FALSE, TRUE),   -- مصروفات
  (504, 'مصاريف التسويق والإعلانات', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (505, 'الرواتب والأجور الإدارية', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (506, 'مصروف إيجار مبنى', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (507, 'مصاريف حكومية', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (508, 'مصاريف عمومية وإدارية', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (509, 'مصروفات تشغيلية (نقاط بيع POS)', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (510, 'مصروفات تشغيلية متغيرة', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (511, 'مصروفات كول سنتر', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (512, 'ديون معدومة', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (513, 'إهلاك سيارات', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (514, 'فوائد ومصاريف تمويلية', 'Expense', 'Dr', FALSE, FALSE),   -- مصروفات
  (515, 'محروقات سيارات', 'Expense', 'Dr', FALSE, FALSE)   -- مصروفات
) AS v(code, name, type, normal_side, is_contra, is_cogs)
WHERE NOT EXISTS (SELECT 1 FROM gl_accounts g WHERE g.code = v.code);

-- ---------- قيد: الأرصدة الافتتاحية وحركات سنة 2024 ----------
-- التاريخ: 2024-12-31 · عدد السطور: 17 · مدين = دائن = 288408.90
DO $$
DECLARE jid gl_journals.id%TYPE;
BEGIN
  IF EXISTS (SELECT 1 FROM gl_journals WHERE entry_date = DATE '2024-12-31' AND description = 'الأرصدة الافتتاحية وحركات سنة 2024') THEN
    RAISE NOTICE 'القيد "%" مُرحَّل مسبقاً — تم تخطّيه', 'الأرصدة الافتتاحية وحركات سنة 2024';
  ELSE
    INSERT INTO gl_journals (entry_date, description)
    VALUES (DATE '2024-12-31', 'الأرصدة الافتتاحية وحركات سنة 2024')
    RETURNING id INTO jid;

    INSERT INTO gl_journal_lines (journal_id, line_no, account_code, debit, credit, memo) VALUES
      (jid, 1, 101, 41302.51, 0.00, NULL),
      (jid, 2, 110, 9000.00, 0.00, NULL),
      (jid, 3, 303, 27834.00, 0.00, NULL),
      (jid, 4, 403, 69.45, 0.00, NULL),
      (jid, 5, 404, 1336.60, 0.00, NULL),
      (jid, 6, 501, 96906.00, 0.00, NULL),
      (jid, 7, 504, 25067.06, 0.00, NULL),
      (jid, 8, 505, 44613.00, 0.00, NULL),
      (jid, 9, 506, 17000.00, 0.00, NULL),
      (jid, 10, 507, 4993.10, 0.00, NULL),
      (jid, 11, 508, 14206.30, 0.00, NULL),
      (jid, 12, 509, 152.15, 0.00, NULL),
      (jid, 13, 510, 5928.73, 0.00, NULL),
      (jid, 14, 301, 0.00, 110739.00, NULL),
      (jid, 15, 304, 0.00, 9138.90, NULL),
      (jid, 16, 401, 0.00, 153930.00, NULL),
      (jid, 17, 402, 0.00, 14601.00, NULL);
  END IF;
END $$;

-- ---------- قيد: حركات وتأثيرات سنة 2025 ----------
-- التاريخ: 2025-12-31 · عدد السطور: 34 · مدين = دائن = 1456315.88
DO $$
DECLARE jid gl_journals.id%TYPE;
BEGIN
  IF EXISTS (SELECT 1 FROM gl_journals WHERE entry_date = DATE '2025-12-31' AND description = 'حركات وتأثيرات سنة 2025') THEN
    RAISE NOTICE 'القيد "%" مُرحَّل مسبقاً — تم تخطّيه', 'حركات وتأثيرات سنة 2025';
  ELSE
    INSERT INTO gl_journals (entry_date, description)
    VALUES (DATE '2025-12-31', 'حركات وتأثيرات سنة 2025')
    RETURNING id INTO jid;

    INSERT INTO gl_journal_lines (journal_id, line_no, account_code, debit, credit, memo) VALUES
      (jid, 1, 101, 94565.32, 0.00, NULL),
      (jid, 2, 103, 54911.00, 0.00, NULL),
      (jid, 3, 104, 7708.00, 0.00, NULL),
      (jid, 4, 105, 4361.41, 0.00, NULL),
      (jid, 5, 110, 129375.00, 0.00, NULL),
      (jid, 6, 112, 27500.00, 0.00, NULL),
      (jid, 7, 113, 77847.21, 0.00, NULL),
      (jid, 8, 304, 5315.70, 0.00, NULL),
      (jid, 9, 403, 21973.57, 0.00, NULL),
      (jid, 10, 404, 4688.00, 0.00, NULL),
      (jid, 11, 501, 393592.00, 0.00, NULL),
      (jid, 12, 502, 124163.00, 0.00, NULL),
      (jid, 13, 503, 5025.00, 0.00, NULL),
      (jid, 14, 504, 241782.59, 0.00, NULL),
      (jid, 15, 505, 119049.97, 0.00, NULL),
      (jid, 16, 506, 17500.00, 0.00, NULL),
      (jid, 17, 507, 23430.00, 0.00, NULL),
      (jid, 18, 508, 44589.60, 0.00, NULL),
      (jid, 19, 509, 1000.00, 0.00, NULL),
      (jid, 20, 510, 37516.72, 0.00, NULL),
      (jid, 21, 511, 7118.79, 0.00, NULL),
      (jid, 22, 512, 1820.00, 0.00, NULL),
      (jid, 23, 513, 6469.00, 0.00, NULL),
      (jid, 24, 514, 4414.00, 0.00, NULL),
      (jid, 25, 515, 600.00, 0.00, NULL),
      (jid, 26, 111, 0.00, 6469.00, NULL),
      (jid, 27, 201, 0.00, 2138.00, NULL),
      (jid, 28, 202, 0.00, 32650.00, NULL),
      (jid, 29, 203, 0.00, 61991.48, NULL),
      (jid, 30, 204, 0.00, 4311.10, NULL),
      (jid, 31, 205, 0.00, 28764.00, NULL),
      (jid, 32, 206, 0.00, 64039.00, NULL),
      (jid, 33, 401, 0.00, 1103983.30, NULL),
      (jid, 34, 402, 0.00, 151970.00, NULL);
  END IF;
END $$;

-- ---------- قيد: حركات وإقفالات النصف الأول 2026 ----------
-- التاريخ: 2026-06-30 · عدد السطور: 31 · مدين = دائن = 930179.40
DO $$
DECLARE jid gl_journals.id%TYPE;
BEGIN
  IF EXISTS (SELECT 1 FROM gl_journals WHERE entry_date = DATE '2026-06-30' AND description = 'حركات وإقفالات النصف الأول 2026') THEN
    RAISE NOTICE 'القيد "%" مُرحَّل مسبقاً — تم تخطّيه', 'حركات وإقفالات النصف الأول 2026';
  ELSE
    INSERT INTO gl_journals (entry_date, description)
    VALUES (DATE '2026-06-30', 'حركات وإقفالات النصف الأول 2026')
    RETURNING id INTO jid;

    INSERT INTO gl_journal_lines (journal_id, line_no, account_code, debit, credit, memo) VALUES
      (jid, 1, 104, 15757.97, 0.00, NULL),
      (jid, 2, 113, 67364.79, 0.00, NULL),
      (jid, 3, 201, 2138.00, 0.00, NULL),
      (jid, 4, 202, 1315.00, 0.00, NULL),
      (jid, 5, 204, 3510.18, 0.00, NULL),
      (jid, 6, 205, 26367.00, 0.00, NULL),
      (jid, 7, 302, 19254.83, 0.00, NULL),
      (jid, 8, 304, 3823.20, 0.00, NULL),
      (jid, 9, 403, 11890.17, 0.00, NULL),
      (jid, 10, 404, 6390.00, 0.00, NULL),
      (jid, 11, 501, 197060.00, 0.00, NULL),
      (jid, 12, 502, 131333.58, 0.00, NULL),
      (jid, 13, 503, 6768.08, 0.00, NULL),
      (jid, 14, 504, 189280.95, 0.00, NULL),
      (jid, 15, 505, 131434.50, 0.00, NULL),
      (jid, 16, 506, 17500.00, 0.00, NULL),
      (jid, 17, 507, 25844.93, 0.00, NULL),
      (jid, 18, 508, 44070.70, 0.00, NULL),
      (jid, 19, 509, 1265.00, 0.00, NULL),
      (jid, 20, 510, 2305.52, 0.00, NULL),
      (jid, 21, 511, 4138.95, 0.00, NULL),
      (jid, 22, 513, 12938.00, 0.00, NULL),
      (jid, 23, 514, 8428.05, 0.00, NULL),
      (jid, 24, 101, 0.00, 50631.09, NULL),
      (jid, 25, 103, 0.00, 29050.00, NULL),
      (jid, 26, 105, 0.00, 4311.10, NULL),
      (jid, 27, 111, 0.00, 12938.00, NULL),
      (jid, 28, 206, 0.00, 22810.43, NULL),
      (jid, 29, 303, 0.00, 27834.00, NULL),
      (jid, 30, 401, 0.00, 782465.91, NULL),
      (jid, 31, 304, 0.00, 138.87, 'تسوية فروق لضبط توازن القيد (فرق وارد من الملف المصدر)');
  END IF;
END $$;

COMMIT;

-- ---------- التحقق بعد الترحيل ----------
-- ميزان المراجعة: يجب أن يتساوى إجمالي المدين مع إجمالي الدائن
SELECT SUM(debit) AS "إجمالي المدين", SUM(credit) AS "إجمالي الدائن",
       SUM(debit) - SUM(credit) AS "الفرق"
FROM gl_journal_lines;

-- توازن كل قيد على حدة
SELECT j.entry_no, j.entry_date, j.description,
       SUM(l.debit) AS debit, SUM(l.credit) AS credit,
       SUM(l.debit) - SUM(l.credit) AS diff
FROM gl_journals j JOIN gl_journal_lines l ON l.journal_id = j.id
GROUP BY j.id, j.entry_no, j.entry_date, j.description
ORDER BY j.entry_date;

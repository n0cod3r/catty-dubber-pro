# HY-MT2-7B-4bit — experimental benchmark

Local MLX 4-bit weights on Apple GPU. Same 16 segments as the earlier benchmark; 32 greedy generations, max 256 new tokens. No automatic quality score. Project unchanged. No promotion to default.

**Timing:** no context 2.39s/segment; contextual 2.59s/segment; total 79.74s. Load and warmup excluded. Runtime/quantization differ from the earlier Transformers baselines.

## 1. 什么陛下要给那个被君为妖魂附身的短命鬼。

Speaker: S1

Previous: (none)

Next: 裴国公赐婚，

Existing gemini (gemini-3.5-flash): ស្អីគេ? ព្រះអម្ចាស់ចង់រៀបការឱ្យអាមនុស្សអាយុខ្លីដែលត្រូវព្រលឹងបិសាចចូលសព្វនោះ?

**HY-MT2 no context:**

តើព្រះអង្គចង់ប្រទានអ្វីដល់អ្នកដែលត្រូវវិញ្ញាណអាក្រក់ចូលសណ្ឋិតនោះ?

**HY-MT2 contextual:**

តើព្រះអង្គចង់ផ្ដល់អ្វីដល់បិសាចដែលមានអាយុខ្លី ហើយត្រូវវិញ្ញាណអាក្រក់ចូលនោះ?

Time: A 3.39s · B 3.96s

## 2. 裴国公赐婚，

Speaker: S1

Previous: 什么陛下要给那个被君为妖魂附身的短命鬼。

Next: 那裴国公虽美貌，

Existing gemini (gemini-3.5-flash): ប្រទានអាពាហ៍ពិពាហ៍ជាមួយលោកកុងប៉េ?

**HY-MT2 no context:**

ព្រះ​អង្គ​ប៉ៃ​ហ្គូកុង បាន​ប្រទាន​អនុញ្ញាត​ឱ្យ​មាន​ការ​រៀប​អាពាហ៍​ពិពាហ៍​នេះ។

**HY-MT2 contextual:**

ព្រះអង្គម្ចាស់ផេយ៍ប្រទានអាពាហ៍ពិពាហ៍។

Time: A 3.39s · B 2.35s

## 4. 性情却暴力阴狠，

Speaker: S1

Previous: 那裴国公虽美貌，

Next: 是个十足的妖精啊，

Existing gemini (gemini-3.5-flash): តែចរិតហិង្សា និងឃោរឃៅខ្លាំងណាស់

**HY-MT2 no context:**

ប៉ុន្តែ​ចរិត​របស់​គេ​វិញ គឺ​ឃោរឃៅ និង​អាក្រក់​ណាស់។

**HY-MT2 contextual:**

ប៉ុន្តែចរិតរបស់គាត់គឺឃោរឃៅ និងហឹង្សា។

Time: A 2.66s · B 2.43s

## 5. 是个十足的妖精啊，

Speaker: S1

Previous: 性情却暴力阴狠，

Next: 妖精听。

Existing gemini (gemini-3.5-flash): ជាបិសាចពិតៗតែម្តង!

**HY-MT2 no context:**

គឺជាបិសាចពិតប្រាកដមែន។

**HY-MT2 contextual:**

គឺជាបិសាចពិតប្រាកដមែន!

Time: A 1.29s · B 1.57s

## 7. 说那裴国公裴修颜乃是九尾妖狐转世以，

Speaker: S1

Previous: 妖精听。

Next: 人心为食不，

Existing gemini (gemini-3.5-flash): គេថា លោកកុងប៉េ ប៉េស៊ាវយ៉ាន នោះ គឺជាកញ្ជ្រោងបិសាចកន្ទុយប្រាំបួនចាប់ជាតិ យក...

**HY-MT2 no context:**

គេនិយាយថា ព្រះ​អង្គ​ប៉ៃ ស៊ីវយ៉ាន់ គឺជាអតីតជាតិរបស់សត្វកញ្ជ្រោងប្រាំបួនកន្ទុយ។

**HY-MT2 contextual:**

គេនិយាយថា ប៉េយ៍ ហ្គូហ្គុង ប៉េយ៍ ស៊ីវយ៉ាន គឺជាការចាប់កំណើតឡើងវិញរបស់សត្វកញ្ជ្រោងអាបធ្មប់មានកន្ទុយប្រាំបួន។

Time: A 4.03s · B 5.49s

## 8. 人心为食不，

Speaker: S1

Previous: 说那裴国公裴修颜乃是九尾妖狐转世以，

Next: 对不对是，

Existing gemini (gemini-3.5-flash): បេះដូងមនុស្សធ្វើជាអាហារ តើមែនទេ? ទេ...

**HY-MT2 no context:**

ចិត្តមនុស្ស គឺសម្រាប់អាហារ។

**HY-MT2 contextual:**

មិនយកចិត្តមនុស្សធ្វើជាអាហារទេ។

Time: A 1.45s · B 1.95s

## 10. 传说中长着翅膀的山海异兽你，

Speaker: S1

Previous: 对不对是，

Next: 们说的都不对而，

Existing gemini (gemini-3.5-flash): ជាសត្វចម្លែកមានស្លាបក្នុងព្រេងនិទានតើ! ពួក...

**HY-MT2 no context:**

តាមរឿងព្រេង មានសត្វចម្លែកដែលមានស្លាប ហើយរស់នៅក្នុងភ្នំនិងសមុទ្រ។

**HY-MT2 contextual:**

សត្វចម្លែកនៅក្នុងរឿងព្រេងដែលមានស្លាប អ្នកឯង،

Time: A 3.28s · B 2.56s

## 13. 水怪啊我。

Speaker: S1

Previous: 是条大蛇是，

Next: 听说夜色之下他，

Existing gemini (gemini-3.5-flash): បិសាចទឹកតើ! ខ្ញុំ

**HY-MT2 no context:**

អាសត្វទឹកអើយ!

**HY-MT2 contextual:**

អាសត្វទឹកអើយខ្ញុំ។

Time: A 0.84s · B 1.43s

## 19. 国公若真是妖怪他又，

Speaker: S1

Previous: 都有尸体抬出可裴。

Next: 怎会那般鄙弱是啊？

Existing gemini (gemini-3.5-flash): កុកកុង បើជាបិសាចមែននោះ ម៉េចក៏

**HY-MT2 no context:**

ប្រសិនបើព្រះអង្គម្ចាស់នោះពិតជាបិសាចមែន នោះវានឹងអញ្ចឹងហើយ។

**HY-MT2 contextual:**

បើសិនជាឧកញ៉ាពិតជាបិសាចមែន តើគាត់ជាអ្វីទៅ?

Time: A 2.94s · B 2.46s

## 21. 太医，

Speaker: S1

Previous: 怎会那般鄙弱是啊？

Next: 们都说他活不过三十岁呢新人，

Existing gemini (gemini-3.5-flash): គ្រូពេទ្យហ្លួង

**HY-MT2 no context:**

គ្រូពេទ្យឯកទេស

**HY-MT2 contextual:**

ពេទ្យរាជ

Time: A 0.93s · B 0.91s

## 27. 会儿在宴会上可不能太出头要是被太夫，

Speaker: S1

Previous: 是要早死啊姐妹们待，

Next: 人看上给裴国公做媳妇儿那可就太惨了上，

Existing gemini (gemini-3.5-flash): នៅក្នុងពិធីជប់លៀង កុំធ្វើខ្លួនលេចធ្លោពេក! ប្រសិនបើលោកជំទាវ...

**HY-MT2 no context:**

នៅក្នុងពិធីជប់លៀងនោះ មិនត្រូវធ្វើខ្លួនឱ្យលេចធ្លោពេកនោះទេ បើមិនដូច្នេះទេ នឹងមានបញ្ហា។

**HY-MT2 contextual:**

បន្តិចទៀតនៅក្នុងពិធីជប់លៀង មិនត្រូវលេចធ្លោពេកទេ បើមិនដូច្នោះទេនឹងត្រូវអ្នកមានអំណាចមើលងាយ។

Time: A 4.55s · B 4.95s

## 28. 人看上给裴国公做媳妇儿那可就太惨了上，

Speaker: S1

Previous: 会儿在宴会上可不能太出头要是被太夫，

Next: 节课你说的是。

Existing gemini (gemini-3.5-flash): មើលភ្នែកត្រូវ យកធ្វើជាប្រពន្ធលោកកុងប៉េ នោះច្បាស់ជាស៊យធំហើយ!

**HY-MT2 no context:**

បើសិនជាមាននរណាម្នាក់ចង់ក្លាយជាភរិយារបស់ព្រះអង្គម្ចាស់ប៉ៃ នោះគឺពិតជាអកុសលខ្លាំងណាស់។

**HY-MT2 contextual:**

បើគេចាប់អារម្មណ៍ចង់ឱ្យធ្វើជាកូនប្រសាររបស់ព្រះអង្គម្ចាស់ប៉េយ នោះពិតជាអកុសលខ្លាំងណាស់។

Time: A 4.09s · B 4.52s

## 32. 吗没有见过吗那你，

Speaker: S2

Previous: 是见到他吃人了你见过，

Next: 见过吗我？

Existing gemini (gemini-3.5-flash): ទេ? អត់ដែលឃើញទេមែនទេ? ចុះឯង...

**HY-MT2 no context:**

មិនធ្លាប់ឃើញទេឬ? អ៊ីចឹងឯង…

**HY-MT2 contextual:**

មែនទេ មិនដែលឃើញទេឬ? អ៊ីចឹងឯង?

Time: A 1.48s · B 2.00s

## 39. 裴府嗯我叫宋之是？

Speaker: S2

Previous: 怪你是何人怎能进了，

Next: 裴国，

Existing gemini (gemini-3.5-flash): ភូមិគ្រឹះផី? អឹម ខ្ញុំឈ្មោះសុងជឺ ជា...

**HY-MT2 no context:**

ផេយ៍ហ្វូ អឺម ខ្ញុំឈ្មោះ សុង ជី មែនទេ?

**HY-MT2 contextual:**

ផ្ទះត្រកូលផេយ អឺម ខ្ញុំឈ្មោះសុង ជីស៊ី មែនទេ?

Time: A 1.90s · B 2.56s

## 41. 公的未婚，

Speaker: S1

Previous: 裴国，

Next: 妻哦未婚妻哪来？

Existing gemini (gemini-3.5-flash): ...ជាគូដណ្តើម...

**HY-MT2 no context:**

បុរសដែលមិនទាន់រៀបការ។

**HY-MT2 contextual:**

បុរសដែលមិនទាន់រៀបការ

Time: A 1.26s · B 1.38s

## 44. 未婚妻啊啊，

Speaker: S2

Previous: 的，

Next: (none)

Existing local (m2m100-1.2b): មិត្តភក្តិរបស់គាត់

**HY-MT2 no context:**

គូដណ្ដឹងអើយ…

**HY-MT2 contextual:**

គូដណ្ដឹងអើយ

Time: A 0.80s · B 0.96s

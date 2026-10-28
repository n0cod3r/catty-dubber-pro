# HY-MT2-1.8B benchmark and 7B comparison

Experimental only. Same 16 segments and project checksum; greedy decoding, 256-token cap. No automatic quality score. Project unchanged.

| Model | Runtime / weights | No context avg | Contextual avg | Total inference |
|---|---|---:|---:|---:|
| Hy-MT2-1.8B | transformers / torch.bfloat16 | 3.54s | 3.39s | 110.80s |
| Hy-MT2-7B-4bit | mlx-lm / 4-bit affine weights, bfloat16 baseline | 2.39s | 2.59s | 79.74s |

Loading and warmup excluded. The 1.8B Transformers run inherits repetition penalty 1.05; the earlier 7B MLX run used 1.0. Different runtimes, quantization and native chat-template tokens mean timing/quality differences cannot be attributed to parameter count alone. Raw results follow.

## 1. 什么陛下要给那个被君为妖魂附身的短命鬼。

Speaker: S1

Previous: (none)

Next: 裴国公赐婚，

Existing gemini (gemini-3.5-flash): ស្អីគេ? ព្រះអម្ចាស់ចង់រៀបការឱ្យអាមនុស្សអាយុខ្លីដែលត្រូវព្រលឹងបិសាចចូលសព្វនោះ?

### HY-MT2-1.8B

**No context:**

តើព្រះអង្គនឹងផ្តល់អ្វីដល់អារក្សដែលមានព្រះបិសាចចូលទៅក្នុងខ្លួននោះ?

**Contextual:**

តើព្រះអង្គនឹងផ្តល់ឱ្យអ្នកដែលត្រូវបានព្រះមហាក្សត្រប្រទានវិញ្ញាណខ្មោច នោះឬ?

Time: A 5.48s · B 5.79s

### HY-MT2-7B-4bit

**No context:**

តើព្រះអង្គចង់ប្រទានអ្វីដល់អ្នកដែលត្រូវវិញ្ញាណអាក្រក់ចូលសណ្ឋិតនោះ?

**Contextual:**

តើព្រះអង្គចង់ផ្ដល់អ្វីដល់បិសាចដែលមានអាយុខ្លី ហើយត្រូវវិញ្ញាណអាក្រក់ចូលនោះ?

Time: A 3.39s · B 3.96s

## 2. 裴国公赐婚，

Speaker: S1

Previous: 什么陛下要给那个被君为妖魂附身的短命鬼。

Next: 那裴国公虽美貌，

Existing gemini (gemini-3.5-flash): ប្រទានអាពាហ៍ពិពាហ៍ជាមួយលោកកុងប៉េ?

### HY-MT2-1.8B

**No context:**

ព្រះអង្គម្ចាស់ ភេ គួកុង ប្រទានអាពាហ៍ពិពាហ៍។

**Contextual:**

ព្រះអង្គម្ចាស់ ភេ ផ្ដល់ការរៀបអាពាហ៍ពិពាហ៍។

Time: A 3.10s · B 3.17s

### HY-MT2-7B-4bit

**No context:**

ព្រះ​អង្គ​ប៉ៃ​ហ្គូកុង បាន​ប្រទាន​អនុញ្ញាត​ឱ្យ​មាន​ការ​រៀប​អាពាហ៍​ពិពាហ៍​នេះ។

**Contextual:**

ព្រះអង្គម្ចាស់ផេយ៍ប្រទានអាពាហ៍ពិពាហ៍។

Time: A 3.39s · B 2.35s

## 4. 性情却暴力阴狠，

Speaker: S1

Previous: 那裴国公虽美貌，

Next: 是个十足的妖精啊，

Existing gemini (gemini-3.5-flash): តែចរិតហិង្សា និងឃោរឃៅខ្លាំងណាស់

### HY-MT2-1.8B

**No context:**

ប៉ុន្តែ ចរិតរបស់វា គឺមានភាពហិង្សា និងអាក្រក់។

**Contextual:**

ប៉ុន្តែចរិតវាមានភាពហិង្សា និងអាក្រក់។

Time: A 3.54s · B 2.97s

### HY-MT2-7B-4bit

**No context:**

ប៉ុន្តែ​ចរិត​របស់​គេ​វិញ គឺ​ឃោរឃៅ និង​អាក្រក់​ណាស់។

**Contextual:**

ប៉ុន្តែចរិតរបស់គាត់គឺឃោរឃៅ និងហឹង្សា។

Time: A 2.66s · B 2.43s

## 5. 是个十足的妖精啊，

Speaker: S1

Previous: 性情却暴力阴狠，

Next: 妖精听。

Existing gemini (gemini-3.5-flash): ជាបិសាចពិតៗតែម្តង!

### HY-MT2-1.8B

**No context:**

គឺជាបិសាចពិតប្រាកដមែន។

**Contextual:**

គឺជាស្រីព្រះដ៏អស្ចារ្យម្នាក់។

Time: A 1.76s · B 2.13s

### HY-MT2-7B-4bit

**No context:**

គឺជាបិសាចពិតប្រាកដមែន។

**Contextual:**

គឺជាបិសាចពិតប្រាកដមែន!

Time: A 1.29s · B 1.57s

## 7. 说那裴国公裴修颜乃是九尾妖狐转世以，

Speaker: S1

Previous: 妖精听。

Next: 人心为食不，

Existing gemini (gemini-3.5-flash): គេថា លោកកុងប៉េ ប៉េស៊ាវយ៉ាន នោះ គឺជាកញ្ជ្រោងបិសាចកន្ទុយប្រាំបួនចាប់ជាតិ យក...

### HY-MT2-1.8B

**No context:**

គេនិយាយថា ព្រះអង្គម្ចាស់ ភេវី ស៊ូយ៉ាន់ គឺជាអ្នកដែលបានចាប់កំណើតឡើងវិញពីសត្វកញ្ជ្រោងដែលមានកន្ទុយប្រាំបួន។

**Contextual:**

និយាយថា លោក ផេ គួងហ្គុង ផេ ស៊ូយ៉ាន គឺជាកូនចៅរបស់សត្វចង្រិតប្រាំបួនកន្ទុយ។

Time: A 7.96s · B 6.06s

### HY-MT2-7B-4bit

**No context:**

គេនិយាយថា ព្រះ​អង្គ​ប៉ៃ ស៊ីវយ៉ាន់ គឺជាអតីតជាតិរបស់សត្វកញ្ជ្រោងប្រាំបួនកន្ទុយ។

**Contextual:**

គេនិយាយថា ប៉េយ៍ ហ្គូហ្គុង ប៉េយ៍ ស៊ីវយ៉ាន គឺជាការចាប់កំណើតឡើងវិញរបស់សត្វកញ្ជ្រោងអាបធ្មប់មានកន្ទុយប្រាំបួន។

Time: A 4.03s · B 5.49s

## 8. 人心为食不，

Speaker: S1

Previous: 说那裴国公裴修颜乃是九尾妖狐转世以，

Next: 对不对是，

Existing gemini (gemini-3.5-flash): បេះដូងមនុស្សធ្វើជាអាហារ តើមែនទេ? ទេ...

### HY-MT2-1.8B

**No context:**

ចិត្តមនុស្សគឺជាអាហារ។

**Contextual:**

ចិត្តមនុស្សជាអាហារ មិនបាន?

Time: A 1.73s · B 2.00s

### HY-MT2-7B-4bit

**No context:**

ចិត្តមនុស្ស គឺសម្រាប់អាហារ។

**Contextual:**

មិនយកចិត្តមនុស្សធ្វើជាអាហារទេ។

Time: A 1.45s · B 1.95s

## 10. 传说中长着翅膀的山海异兽你，

Speaker: S1

Previous: 对不对是，

Next: 们说的都不对而，

Existing gemini (gemini-3.5-flash): ជាសត្វចម្លែកមានស្លាបក្នុងព្រេងនិទានតើ! ពួក...

### HY-MT2-1.8B

**No context:**

តាមរឿងព្រេង សត្វដែលមានស្លាប និងរស់នៅលើសមុទ្រ អ្នក…

**Contextual:**

អ្នកដែលជាសត្វចម្លែកដែលមានស្លាបនៅក្នុងរឿងព្រេងនិទាន

Time: A 4.03s · B 4.30s

### HY-MT2-7B-4bit

**No context:**

តាមរឿងព្រេង មានសត្វចម្លែកដែលមានស្លាប ហើយរស់នៅក្នុងភ្នំនិងសមុទ្រ។

**Contextual:**

សត្វចម្លែកនៅក្នុងរឿងព្រេងដែលមានស្លាប អ្នកឯង،

Time: A 3.28s · B 2.56s

## 13. 水怪啊我。

Speaker: S1

Previous: 是条大蛇是，

Next: 听说夜色之下他，

Existing gemini (gemini-3.5-flash): បិសាចទឹកតើ! ខ្ញុំ

### HY-MT2-1.8B

**No context:**

សត្វសមុទ្រអើយ…

**Contextual:**

សត្វអណ្ដាតទឹកអើយ ខ្ញុំ។

Time: A 1.35s · B 2.01s

### HY-MT2-7B-4bit

**No context:**

អាសត្វទឹកអើយ!

**Contextual:**

អាសត្វទឹកអើយខ្ញុំ។

Time: A 0.84s · B 1.43s

## 19. 国公若真是妖怪他又，

Speaker: S1

Previous: 都有尸体抬出可裴。

Next: 怎会那般鄙弱是啊？

Existing gemini (gemini-3.5-flash): កុកកុង បើជាបិសាចមែននោះ ម៉េចក៏

### HY-MT2-1.8B

**No context:**

ប្រសិនបើជាសត្វចម្លែកពិតមែន គាត់នោះ…

**Contextual:**

ប្រសិនបើអ្នកជាបិសាចពិតមែន គាត់នឹង…

Time: A 3.00s · B 2.89s

### HY-MT2-7B-4bit

**No context:**

ប្រសិនបើព្រះអង្គម្ចាស់នោះពិតជាបិសាចមែន នោះវានឹងអញ្ចឹងហើយ។

**Contextual:**

បើសិនជាឧកញ៉ាពិតជាបិសាចមែន តើគាត់ជាអ្វីទៅ?

Time: A 2.94s · B 2.46s

## 21. 太医，

Speaker: S1

Previous: 怎会那般鄙弱是啊？

Next: 们都说他活不过三十岁呢新人，

Existing gemini (gemini-3.5-flash): គ្រូពេទ្យហ្លួង

### HY-MT2-1.8B

**No context:**

គ្រូពេទ្យវេជ្ជសាស្ត្រ

**Contextual:**

ប្រធានគ្រូពេទ្យ,

Time: A 1.58s · B 1.32s

### HY-MT2-7B-4bit

**No context:**

គ្រូពេទ្យឯកទេស

**Contextual:**

ពេទ្យរាជ

Time: A 0.93s · B 0.91s

## 27. 会儿在宴会上可不能太出头要是被太夫，

Speaker: S1

Previous: 是要早死啊姐妹们待，

Next: 人看上给裴国公做媳妇儿那可就太惨了上，

Existing gemini (gemini-3.5-flash): នៅក្នុងពិធីជប់លៀង កុំធ្វើខ្លួនលេចធ្លោពេក! ប្រសិនបើលោកជំទាវ...

### HY-MT2-1.8B

**No context:**

នៅក្នុងពិធីជប់លៀង មិនអាចធ្វើខ្លួនឱ្យលេចធ្លោពេកនោះទេ បើសិនជាត្រូវគេស្គាល់ថា ជាមនុស្សដែលមានភាពលេចធ្លោពេក។

**Contextual:**

នៅក្នុងពិធីជប់លៀង មិនអាចធ្វើខ្លួនឱ្យលេចធ្លោពេកទេ បើត្រូវបានថៃហ្វឺ។

Time: A 8.56s · B 5.99s

### HY-MT2-7B-4bit

**No context:**

នៅក្នុងពិធីជប់លៀងនោះ មិនត្រូវធ្វើខ្លួនឱ្យលេចធ្លោពេកនោះទេ បើមិនដូច្នេះទេ នឹងមានបញ្ហា។

**Contextual:**

បន្តិចទៀតនៅក្នុងពិធីជប់លៀង មិនត្រូវលេចធ្លោពេកទេ បើមិនដូច្នោះទេនឹងត្រូវអ្នកមានអំណាចមើលងាយ។

Time: A 4.55s · B 4.95s

## 28. 人看上给裴国公做媳妇儿那可就太惨了上，

Speaker: S1

Previous: 会儿在宴会上可不能太出头要是被太夫，

Next: 节课你说的是。

Existing gemini (gemini-3.5-flash): មើលភ្នែកត្រូវ យកធ្វើជាប្រពន្ធលោកកុងប៉េ នោះច្បាស់ជាស៊យធំហើយ!

### HY-MT2-1.8B

**No context:**

ការដែលត្រូវធ្វើជាប្រពន្ធរបស់ព្រះអង្គម្ចាស់ភេអ៊ី គឺជារឿងដ៏អាក្រក់ណាស់។

**Contextual:**

ប្រសិនបើគេចង់យកអ្នកណាម្នាក់ធ្វើជាប្រពន្ធរបស់លោកប៉េ គឺវាពិតជាអយុត្តិធម៌ណាស់។

Time: A 5.57s · B 6.19s

### HY-MT2-7B-4bit

**No context:**

បើសិនជាមាននរណាម្នាក់ចង់ក្លាយជាភរិយារបស់ព្រះអង្គម្ចាស់ប៉ៃ នោះគឺពិតជាអកុសលខ្លាំងណាស់។

**Contextual:**

បើគេចាប់អារម្មណ៍ចង់ឱ្យធ្វើជាកូនប្រសាររបស់ព្រះអង្គម្ចាស់ប៉េយ នោះពិតជាអកុសលខ្លាំងណាស់។

Time: A 4.09s · B 4.52s

## 32. 吗没有见过吗那你，

Speaker: S2

Previous: 是见到他吃人了你见过，

Next: 见过吗我？

Existing gemini (gemini-3.5-flash): ទេ? អត់ដែលឃើញទេមែនទេ? ចុះឯង...

### HY-MT2-1.8B

**No context:**

មិនដែលឃើញទេឬ? ចុះអ្នកវិញ…

**Contextual:**

មែនទេ? មិនបានឃើញទេឬ? ដូច្នេះ អ្នក…

Time: A 2.32s · B 2.96s

### HY-MT2-7B-4bit

**No context:**

មិនធ្លាប់ឃើញទេឬ? អ៊ីចឹងឯង…

**Contextual:**

មែនទេ មិនដែលឃើញទេឬ? អ៊ីចឹងឯង?

Time: A 1.48s · B 2.00s

## 39. 裴府嗯我叫宋之是？

Speaker: S2

Previous: 怪你是何人怎能进了，

Next: 裴国，

Existing gemini (gemini-3.5-flash): ភូមិគ្រឹះផី? អឹម ខ្ញុំឈ្មោះសុងជឺ ជា...

### HY-MT2-1.8B

**No context:**

ផេហ្វូ អូហ៍ ខ្ញុំឈ្មោះ សុងជី មែនទេ?

**Contextual:**

ផេហ្វូ អើយ ខ្ញុំឈ្មោះ សុង ជីស៊ី?

Time: A 3.04s · B 3.03s

### HY-MT2-7B-4bit

**No context:**

ផេយ៍ហ្វូ អឺម ខ្ញុំឈ្មោះ សុង ជី មែនទេ?

**Contextual:**

ផ្ទះត្រកូលផេយ អឺម ខ្ញុំឈ្មោះសុង ជីស៊ី មែនទេ?

Time: A 1.90s · B 2.56s

## 41. 公的未婚，

Speaker: S1

Previous: 裴国，

Next: 妻哦未婚妻哪来？

Existing gemini (gemini-3.5-flash): ...ជាគូដណ្តើម...

### HY-MT2-1.8B

**No context:**

អ្នកស្រីមិនទាន់រៀបការនៅឡើយ។

**Contextual:**

ប្តីមិនរៀបការនៅឡើយ។

Time: A 2.38s · B 1.83s

### HY-MT2-7B-4bit

**No context:**

បុរសដែលមិនទាន់រៀបការ។

**Contextual:**

បុរសដែលមិនទាន់រៀបការ

Time: A 1.26s · B 1.38s

## 44. 未婚妻啊啊，

Speaker: S2

Previous: 的，

Next: (none)

Existing local (m2m100-1.2b): មិត្តភក្តិរបស់គាត់

### HY-MT2-1.8B

**No context:**

មិត្តស្រីអើយ…

**Contextual:**

អូនស្រីស្រីស្នេហ៍!

Time: A 1.18s · B 1.58s

### HY-MT2-7B-4bit

**No context:**

គូដណ្ដឹងអើយ…

**Contextual:**

គូដណ្ដឹងអើយ

Time: A 0.80s · B 0.96s


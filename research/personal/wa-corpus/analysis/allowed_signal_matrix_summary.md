# Allowed Signal Matrix Summary

- Generated UTC: `2026-05-26T13:56:53+00:00`
- Input DB: `allowed_signal_hits.local.sqlite`
- Matrix DB: `allowed_signal_matrix.local.sqlite`
- Signal hits read: `12249`
- Privacy boundary: reads only `file_id`, `source_tag`, `message_index`, `timestamp`, and `signal_code` from `signal_hits`.

## Signal Totals

| signal_code          | hit_count | file_count | message_count |
| -------------------- | --------- | ---------- | ------------- |
| immigration          | 3174      | 31         | 3174          |
| contains_phone_like  | 2777      | 31         | 2777          |
| identity_document    | 2170      | 31         | 2170          |
| scheduling_followup  | 915       | 31         | 915           |
| tax_accounting       | 778       | 31         | 778           |
| bahasa_operational   | 669       | 27         | 669           |
| company_corporate    | 629       | 30         | 629           |
| urgency_risk         | 406       | 31         | 406           |
| money_like           | 319       | 31         | 319           |
| contains_url         | 205       | 30         | 205           |
| property_real_estate | 146       | 22         | 146           |
| contains_email       | 61        | 20         | 61            |

## Signal x Source Tag

| signal_code          | source_tag     | hit_count | file_count | message_count |
| -------------------- | -------------- | --------- | ---------- | ------------- |
| immigration          | tag-f6302850cc | 1198      | 10         | 1198          |
| contains_phone_like  | tag-f6302850cc | 1128      | 10         | 1128          |
| immigration          | tag-f4c6a73c2c | 1075      | 10         | 1075          |
| contains_phone_like  | tag-f4c6a73c2c | 1047      | 10         | 1047          |
| identity_document    | tag-f6302850cc | 935       | 10         | 935           |
| immigration          | tag-02a8764847 | 901       | 11         | 901           |
| identity_document    | tag-f4c6a73c2c | 828       | 10         | 828           |
| contains_phone_like  | tag-02a8764847 | 602       | 11         | 602           |
| identity_document    | tag-02a8764847 | 407       | 11         | 407           |
| scheduling_followup  | tag-f4c6a73c2c | 378       | 10         | 378           |
| tax_accounting       | tag-f6302850cc | 374       | 10         | 374           |
| bahasa_operational   | tag-02a8764847 | 336       | 11         | 336           |
| scheduling_followup  | tag-02a8764847 | 299       | 11         | 299           |
| company_corporate    | tag-f6302850cc | 276       | 10         | 276           |
| tax_accounting       | tag-02a8764847 | 248       | 11         | 248           |
| bahasa_operational   | tag-f6302850cc | 243       | 8          | 243           |
| scheduling_followup  | tag-f6302850cc | 238       | 10         | 238           |
| company_corporate    | tag-f4c6a73c2c | 204       | 9          | 204           |
| money_like           | tag-f6302850cc | 181       | 10         | 181           |
| tax_accounting       | tag-f4c6a73c2c | 156       | 10         | 156           |
| urgency_risk         | tag-f4c6a73c2c | 154       | 10         | 154           |
| company_corporate    | tag-02a8764847 | 149       | 11         | 149           |
| urgency_risk         | tag-02a8764847 | 130       | 11         | 130           |
| urgency_risk         | tag-f6302850cc | 122       | 10         | 122           |
| property_real_estate | tag-f6302850cc | 105       | 9          | 105           |

_Showing 25 of 36 rows._

## Signal x Month

| signal_code         | month   | hit_count | file_count | message_count |
| ------------------- | ------- | --------- | ---------- | ------------- |
| immigration         | 2026-01 | 312       | 21         | 312           |
| immigration         | 2026-03 | 286       | 23         | 286           |
| contains_phone_like | 2026-01 | 278       | 19         | 278           |
| immigration         | 2025-09 | 262       | 19         | 262           |
| immigration         | 2025-10 | 250       | 24         | 250           |
| identity_document   | 2026-01 | 217       | 19         | 217           |
| contains_phone_like | 2025-04 | 205       | 12         | 205           |
| contains_phone_like | 2026-03 | 199       | 22         | 199           |
| immigration         | 2025-12 | 189       | 21         | 189           |
| contains_phone_like | 2025-09 | 180       | 15         | 180           |
| contains_phone_like | 2026-04 | 173       | 20         | 173           |
| contains_phone_like | 2026-02 | 172       | 17         | 172           |
| immigration         | 2026-02 | 172       | 17         | 172           |
| immigration         | 2025-07 | 170       | 16         | 170           |
| immigration         | 2025-04 | 169       | 10         | 169           |
| identity_document   | 2026-03 | 164       | 21         | 164           |
| immigration         | 2025-08 | 162       | 17         | 162           |
| identity_document   | 2025-09 | 156       | 16         | 156           |
| contains_phone_like | 2025-12 | 153       | 17         | 153           |
| immigration         | 2025-05 | 148       | 15         | 148           |
| immigration         | 2026-04 | 147       | 24         | 147           |
| contains_phone_like | 2025-06 | 144       | 11         | 144           |
| contains_phone_like | 2025-11 | 144       | 15         | 144           |
| immigration         | 2025-06 | 143       | 12         | 143           |
| immigration         | 2025-11 | 137       | 16         | 137           |

_Showing 25 of 302 rows._

## Per-File Signal Density

| file_id      | source_tag     | total_hits | hit_message_count | message_span | hits_per_hit_message | hits_per_message_span |
| ------------ | -------------- | ---------- | ----------------- | ------------ | -------------------- | --------------------- |
| wa-file-0576 | tag-f4c6a73c2c | 381        | 235               | 405          | 1.621277             | 0.940741              |
| wa-file-0630 | tag-02a8764847 | 345        | 253               | 384          | 1.363636             | 0.898438              |
| wa-file-0293 | tag-f6302850cc | 484        | 311               | 552          | 1.55627              | 0.876812              |
| wa-file-0294 | tag-f6302850cc | 484        | 311               | 552          | 1.55627              | 0.876812              |
| wa-file-0297 | tag-f6302850cc | 512        | 327               | 666          | 1.565749             | 0.768769              |
| wa-file-0628 | tag-02a8764847 | 712        | 455               | 931          | 1.564835             | 0.764769              |
| wa-file-0305 | tag-f6302850cc | 969        | 681               | 1323         | 1.422907             | 0.732426              |
| wa-file-0313 | tag-f6302850cc | 1157       | 783               | 1668         | 1.47765              | 0.693645              |
| wa-file-0558 | tag-f4c6a73c2c | 187        | 126               | 289          | 1.484127             | 0.647059              |
| wa-file-0547 | tag-f4c6a73c2c | 267        | 168               | 415          | 1.589286             | 0.643373              |
| wa-file-0538 | tag-f4c6a73c2c | 221        | 142               | 346          | 1.556338             | 0.638728              |
| wa-file-0634 | tag-02a8764847 | 319        | 236               | 510          | 1.351695             | 0.62549               |
| wa-file-0291 | tag-f6302850cc | 316        | 192               | 516          | 1.645833             | 0.612403              |
| wa-file-0317 | tag-f6302850cc | 206        | 137               | 349          | 1.50365              | 0.590258              |
| wa-file-0553 | tag-f4c6a73c2c | 322        | 217               | 547          | 1.483871             | 0.588665              |
| wa-file-0579 | tag-f4c6a73c2c | 1985       | 1413              | 3436         | 1.404812             | 0.577707              |
| wa-file-0633 | tag-02a8764847 | 263        | 187               | 461          | 1.406417             | 0.570499              |
| wa-file-0300 | tag-f6302850cc | 205        | 135               | 364          | 1.518519             | 0.563187              |
| wa-file-0548 | tag-f4c6a73c2c | 163        | 109               | 317          | 1.495413             | 0.514196              |
| wa-file-0598 | tag-02a8764847 | 204        | 143               | 397          | 1.426573             | 0.513854              |
| wa-file-0568 | tag-f4c6a73c2c | 188        | 138               | 366          | 1.362319             | 0.513661              |
| wa-file-0295 | tag-f6302850cc | 260        | 185               | 511          | 1.405405             | 0.508806              |
| wa-file-0541 | tag-f4c6a73c2c | 173        | 129               | 359          | 1.341085             | 0.481894              |
| wa-file-0627 | tag-02a8764847 | 380        | 255               | 791          | 1.490196             | 0.480405              |
| wa-file-0607 | tag-02a8764847 | 169        | 121               | 353          | 1.396694             | 0.478754              |

_Showing 25 of 31 rows._

## Signal Co-Occurrence

| signal_code_a       | signal_code_b       | message_count | file_count |
| ------------------- | ------------------- | ------------- | ---------- |
| contains_phone_like | identity_document   | 1218          | 31         |
| identity_document   | immigration         | 542           | 31         |
| contains_phone_like | immigration         | 250           | 31         |
| company_corporate   | immigration         | 247           | 29         |
| immigration         | scheduling_followup | 237           | 31         |
| immigration         | tax_accounting      | 229           | 31         |
| immigration         | money_like          | 222           | 31         |
| immigration         | urgency_risk        | 201           | 30         |
| identity_document   | money_like          | 197           | 30         |
| identity_document   | tax_accounting      | 159           | 29         |
| company_corporate   | identity_document   | 146           | 26         |
| bahasa_operational  | immigration         | 129           | 23         |
| contains_url        | immigration         | 123           | 30         |
| money_like          | tax_accounting      | 108           | 27         |
| contains_url        | identity_document   | 103           | 28         |
| identity_document   | scheduling_followup | 101           | 28         |
| company_corporate   | tax_accounting      | 96            | 22         |
| company_corporate   | money_like          | 93            | 27         |
| identity_document   | urgency_risk        | 93            | 28         |
| scheduling_followup | tax_accounting      | 91            | 26         |
| contains_phone_like | tax_accounting      | 85            | 29         |
| company_corporate   | contains_phone_like | 74            | 23         |
| bahasa_operational  | identity_document   | 73            | 23         |
| contains_url        | scheduling_followup | 54            | 21         |
| money_like          | urgency_risk        | 52            | 24         |

_Showing 25 of 63 rows._

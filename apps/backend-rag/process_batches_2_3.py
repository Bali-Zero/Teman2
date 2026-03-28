import asyncio
import json
import logging
import os
import sys
from typing import Any

import httpx
import pdfplumber
from anthropic import AsyncAnthropic

# Add backend to path
sys.path.append("/Users/nuzantara/Desktop/nuzantara/apps/backend-rag")

# Nuzantara imports
from backend.services.integrations.drive.drive_auth import DriveAuthManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchProcessor")

# Constants
RESULTS_DIR = "/Users/nuzantara/Desktop/nuzantara/.gemini/tmp/results"
PDF_DIR = os.path.join(RESULTS_DIR, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

BATCH_2 = [{'company_id': 2164, 'name': 'PT Mcmillan Indonesian Investment Group', 'drive_file_id': '1iPrXJoTwy6KU70THjnxcyXiQTA2rYIK1'}, {'company_id': 2167, 'name': 'PT Mediterraneo Boutique Resort', 'drive_file_id': '1WADsHcoQNQg4fEjwOM6yOXK-KbcsorEn'}, {'company_id': 2168, 'name': 'PT Mega Jaya Tirta', 'drive_file_id': '1pD1Udt8hrQlV0fPFs2rclueeXlXLQHIU'}, {'company_id': 2169, 'name': 'PT Mega Trade Group', 'drive_file_id': '1EBjn3yvnlEui2UYgCkbwXuuB2lQef6U_'}, {'company_id': 2170, 'name': 'PT Megah Sentosa Properti', 'drive_file_id': '1QIEaLXk2WSjKUiJp5RjvOyXsMnACDRsB'}, {'company_id': 2171, 'name': 'PT Megi Media Consulting', 'drive_file_id': '1gKD8WSmhC3JN6vPTUBnh1_TChjgeEYUz'}, {'company_id': 2172, 'name': 'PT Melba Partners Bali', 'drive_file_id': '1fcRbverHge0cAyH718fv7VYZDZgAvRP0'}, {'company_id': 2172, 'name': 'PT Melba Partners Bali', 'drive_file_id': '1TscG8OacfboRGzH3QOBjxq_U2YxsRVLW'}, {'company_id': 2173, 'name': 'PT Mellow Boutique Bali', 'drive_file_id': '1TN7fiWbUW72BwktfwZ3pYjWbwJwVi7-c'}, {'company_id': 2174, 'name': 'PT Melograno Fusion Bali', 'drive_file_id': '1auEMGXRRZlWbTWzVk0SHBYR0IjBKoY6G'}, {'company_id': 2174, 'name': 'PT Melograno Fusion Bali', 'drive_file_id': '1WKmv2VwTlmEkQl4V-PkmBlwwYCN2FwUE'}, {'company_id': 2177, 'name': 'PT Merah Bisma Ubud PT (Bu Wira)', 'drive_file_id': '1sQwtR1wwGWF1N5jA821TckqTF5-UN2QY'}, {'company_id': 2277, 'name': 'PT Nusa Futura Wan', 'drive_file_id': '1eTNByTFToJGegHey4JONpJFQivKMsTkK'}, {'company_id': 2278, 'name': 'PT Nusa Tropic Logistics', 'drive_file_id': '19FgmdV2OqSPBYhtKZLKrwT5-S3D9xDil'}, {'company_id': 2311, 'name': 'PT Gavin Autterson Media Management', 'drive_file_id': '1PQIjBgCysKMsE9B1M8segXg15odMHgYC'}, {'company_id': 2311, 'name': 'PT Gavin Autterson Media Management', 'drive_file_id': '1RCBdViHEi5vsPcFbFetmFD5WHajlQn36'}, {'company_id': 2312, 'name': 'PT Hannah Sainte Julie', 'drive_file_id': '14zmb5tbZ1Xvqce22Si32Nw9bPuyXnCTy'}, {'company_id': 2314, 'name': 'PT Take Bali Dream', 'drive_file_id': '12bGhA7Njvzs4B3ElshPahgWPJL0NObdo'}, {'company_id': 2314, 'name': 'PT Take Bali Dream', 'drive_file_id': '1hzcHghqGs5HBtWG2yPj4g5zZ1RLU0KrK'}, {'company_id': 2314, 'name': 'PT Take Bali Dream', 'drive_file_id': '1jvnYiYmwJtcsfUrAHCTzw-NbDP9qEuRq'}, {'company_id': 2315, 'name': 'Ombak Buah Bali', 'drive_file_id': '1eL2F037GSnteZBLrdFcVZKktgr9DlJtR'}, {'company_id': 2316, 'name': 'PT Bali Social Raket', 'drive_file_id': '1Ie_iVQjMFl9Zboi2dlT0HegvcoyfhJ1i'}, {'company_id': 2316, 'name': 'PT Bali Social Raket', 'drive_file_id': '1qpc6gOQrEeoxf3p-SfIuN47VBH8dR5Mw'}, {'company_id': 2317, 'name': 'PT Tropikal Bali Group', 'drive_file_id': '1JOXrAMRiXfWN0Qma5DwTX-np5kzOn267'}, {'company_id': 2317, 'name': 'PT Tropikal Bali Group', 'drive_file_id': '1m-MOmC5XFFIu42kOxZMadkMFnsBLH6AZ'}, {'company_id': 2319, 'name': 'PT The Fontanas Group', 'drive_file_id': '1dfxqH-oy1foLzJFBr_-JJfohGNBIrLua'}, {'company_id': 2320, 'name': 'PT Veni Vidi Vichi', 'drive_file_id': '1lBZcvgT5c-K3QD_P2mlYoScBnXoamywb'}, {'company_id': 2322, 'name': 'PT Bplus Cafe Bali', 'drive_file_id': '15C-nZUXOPU98UaY7OXSBoAbaOjPJPKuQ'}, {'company_id': 2322, 'name': 'PT Bplus Cafe Bali', 'drive_file_id': '1GHtXdHVJVggTtDQi0kM8dIFU3YdlhkOE'}, {'company_id': 2323, 'name': 'PT Pura Cucina Studio', 'drive_file_id': '1kj2azSRTNxfu2NnI9DXDP_EMdeJObItz'}, {'company_id': 2323, 'name': 'PT Pura Cucina Studio', 'drive_file_id': '1n16edLXTH3NTyOsN4gbk61aySXwQwmUy'}, {'company_id': 2324, 'name': 'PT Unikorn Bali Home', 'drive_file_id': '1Kb5cbMfr6NBLPXmR_VUWFJRBw3JbQLEx'}, {'company_id': 2326, 'name': 'PT Tropico Super Tech', 'drive_file_id': '15uLrYhVA0S01aHS7WEePIQ1xbBniSb76'}, {'company_id': 2326, 'name': 'PT Tropico Super Tech', 'drive_file_id': '19dFBxQdTTLOCQrG5VDIqUTcz1-9yL3lx'}, {'company_id': 2326, 'name': 'PT Tropico Super Tech', 'drive_file_id': '1p4hJNBWeg0rKRkTy6drCQt6QPSOqlS-J'}, {'company_id': 2326, 'name': 'PT Tropico Super Tech', 'drive_file_id': '1ut0H4tL848a4vaw9NlVqiR0ghulNL4EF'}, {'company_id': 2327, 'name': 'PT Hang Loose Compagny', 'drive_file_id': '1oc-1CRbYD_bkhqg5N298kOFnpoJMAIjy'}, {'company_id': 2328, 'name': 'PT Ropek Media Consulting', 'drive_file_id': '1xHldjRImg7vLx2-dmRnsHJMsdDXCDs5X'}, {'company_id': 2329, 'name': 'PT Bram Makanan Collective', 'drive_file_id': '13st9r5oiFYl_Nu_4MvNjt9fwERbZheNZ'}, {'company_id': 2330, 'name': 'PT One Blue Ocean', 'drive_file_id': '1cjED6Yd9PKQj2Iqadlh6thPlpcmEAWL6'}, {'company_id': 2331, 'name': 'PT Cerita From Earthsea', 'drive_file_id': '1LwJXwCfqzROJsKBEEo1Sk6Yx6Dd4ClAG'}, {'company_id': 2333, 'name': 'PT Global Canvas Collective', 'drive_file_id': '121dpFpMqjdoNOluJEI-633iEXA8EauOq'}, {'company_id': 2334, 'name': 'PT Wirramanda Artist Recovery', 'drive_file_id': '1FRPeJLq4gUoGCEZXjmULA5f5aHyKMwxY'}, {'company_id': 2336, 'name': 'PT Bali Bliss Travel', 'drive_file_id': '1PdSCmCHYNz8WkCLctqLuFTzSZhorAiNN'}, {'company_id': 2336, 'name': 'PT Bali Bliss Travel', 'drive_file_id': '1SoI7tzGm-PcLTo5RGsuu_WcHuPzsRnTe'}, {'company_id': 2336, 'name': 'PT Bali Bliss Travel', 'drive_file_id': '1usdLfVC_ymC0YNfhB3wHfzd0O66-kzqx'}, {'company_id': 2336, 'name': 'PT Bali Bliss Travel', 'drive_file_id': '1ydCLweGW4mcg967i-rgTU2doZaFrhx8s'}, {'company_id': 2337, 'name': 'PT Vitalitas Bali Fcp', 'drive_file_id': '1GEqaZCgped0NmfeHD6akJUeqDm70PBXT'}, {'company_id': 2338, 'name': 'PT The Tree House', 'drive_file_id': '1F_3Ml50LGASIDWhJwR2unf9ktWSIAZKz'}, {'company_id': 2338, 'name': 'PT The Tree House', 'drive_file_id': '1KvWsPPd6QD9vHaOAk039DEDlk8RdCAUt'}, {'company_id': 2339, 'name': 'PT The Rizing Sol', 'drive_file_id': '1ZUGf2QcnjK8sTkqvngiIZWQjr4YoMFZ3'}, {'company_id': 2340, 'name': 'PT Vision Marketing Consulting Group', 'drive_file_id': '1i213BimgAhUcKXFF-FSNAayhbpskRIKF'}, {'company_id': 2341, 'name': 'PT Mimpi Biru Besar', 'drive_file_id': '1GDQ5m027fffMxTGOfn4dYcXA3JckSXFN'}, {'company_id': 2342, 'name': 'PT Tilli Kecil Dua', 'drive_file_id': '1KO_I0vIG9yVWs2_vIn_t5hnDAjdj70hD'}, {'company_id': 2342, 'name': 'PT Tilli Kecil Dua', 'drive_file_id': '1nro6WZAkwwjxfKO2nDfMmAUkztGSQrRv'}, {'company_id': 2347, 'name': 'PT Sannyas Retreats Bali', 'drive_file_id': '1Cp3PjUCFzVI1KZeNCVk7vmRT-QSfvIuH'}, {'company_id': 2347, 'name': 'PT Sannyas Retreats Bali', 'drive_file_id': '1gku_BlrDcyW4yRTOtBf09fjHxZEy_z3Z'}, {'company_id': 2383, 'name': 'PT Nelson Surf Spot', 'drive_file_id': '1MEffvWysE0XwFXVvF2OJX0H-SxydpRe2'}, {'company_id': 2401, 'name': 'PT Timeless Investment Spaces', 'drive_file_id': '12zMo6xuM8uust702GdOM4Zgk3vyjfQuc'}, {'company_id': 2446, 'name': 'PT World Cobianc Cardenas', 'drive_file_id': '1pkqU6TJuhfOkE7gDNBh-9omomp9kUGk_'}, {'company_id': 2480, 'name': 'PT Wanderlands Management Group', 'drive_file_id': '18chbW1pLTqJYRnZMDTFlilrMCehdHTZ5'}, {'company_id': 2480, 'name': 'PT Wanderlands Management Group', 'drive_file_id': '1AOkSdEGEJUkEowMNjOQP_v6L5P7yuoH7'}, {'company_id': 2480, 'name': 'PT Wanderlands Management Group', 'drive_file_id': '1MQ0Ppk7hdnYVGPmU9na1CB0GGAStBx2'}, {'company_id': 2496, 'name': 'PT Virgo Investment Consulting', 'drive_file_id': '1ikYUR2qHiImhwjkmOp-cm0Lb3Rb5RtSv'}, {'company_id': 2496, 'name': 'PT Virgo Investment Consulting', 'drive_file_id': '1JHpMzjcm5_fIbk4xbSdD557apChqz53y'}, {'company_id': 2496, 'name': 'PT Virgo Investment Consulting', 'drive_file_id': '1MHGyQexskKmxIU7O7qdzl-PGDaYCcDni'}, {'company_id': 2502, 'name': 'PT Vir Ain Ben', 'drive_file_id': '19RImo2nEF0pDCoZcocXH2XwcIh-zJCnV'}, {'company_id': 2508, 'name': 'PT Vertical Indonesia Group', 'drive_file_id': '1vSYbWUEAzxfJoYTZJaaxlIPOc6nWueTH'}, {'company_id': 2510, 'name': 'PT Vendo Enso Asia', 'drive_file_id': '10LlLLm5Ct-LRelN7X1Hnusi2DcNYRWWm'}, {'company_id': 2510, 'name': 'PT Vendo Enso Asia', 'drive_file_id': '1loIxubeYbnxSmbJMEYWXNuNgijPWJoEU'}, {'company_id': 2511, 'name': 'PT Valerii Veronika Investments', 'drive_file_id': '1MnCpJFHDjn3ofqfB29aZAu2jsTn-LBjO'}, {'company_id': 2513, 'name': 'PT Valencia Bali Kuliner', 'drive_file_id': '10hxCBWaDr4AwpDjYHMhbTlj8Ow_9vBbl'}, {'company_id': 2518, 'name': 'PT Usu Bali Group', 'drive_file_id': '1gpvUQpJpScvg2Z-qUgM_hCUGtVGom7Il'}, {'company_id': 2520, 'name': 'PT Urban Jungle Bali', 'drive_file_id': '1dALpjE58YTaGO-FbcbSGvU53zE9e5lxg'}, {'company_id': 2522, 'name': 'PT Upgrade People Indonesia', 'drive_file_id': '1675-YiTtJTSdLgAhJlc6bXGu7gD49TXZ'}, {'company_id': 2524, 'name': 'PT Unrivalled Being Bali', 'drive_file_id': '13WaGzQs-htdoR66SnXKoWaIMy5lPWpCf'}]

BATCH_3 = [{'company_id': 2526, 'name': 'PT Unity Land Development', 'drive_file_id': '1H-aFHxMFmjswZtXYMlALvWsE_vyPhKlk'}, {'company_id': 2528, 'name': 'PT Umamu Projects Collective', 'drive_file_id': '1ulHVvTnWYYTwY68AEYwM9f1VvzTMmH1X'}, {'company_id': 2529, 'name': 'PT Unicorn Properties Estate', 'drive_file_id': '11BHwFcWYY3M9UUZc9uR3ojqP4K7Qg9IN'}, {'company_id': 2530, 'name': 'PT Uluwatu Wooden Bali', 'drive_file_id': '1-5M83lFQCcu50ePRd6ZLGyCuDBlUmUOL'}, {'company_id': 2530, 'name': 'PT Uluwatu Wooden Bali', 'drive_file_id': '1Cha76Dv5b61nJMuL0NbMmH1CLdz9tQu_'}, {'company_id': 2530, 'name': 'PT Uluwatu Wooden Bali', 'drive_file_id': '1-VU4-JYOye9jletazjiZgvq1N0tZVPqT'}, {'company_id': 2533, 'name': 'PT Ukrainian Soul Concept', 'drive_file_id': '1gxUcoKpi2kmKhdGVINqmjRWDMlbBjTKd'}, {'company_id': 2533, 'name': 'PT Ukrainian Soul Concept', 'drive_file_id': '1-zy_YBmWkzpi8ZYYXqMvKGEY-kQ8RVzo'}, {'company_id': 2536, 'name': 'PT Ubuntu Residences Real Estat', 'drive_file_id': '1FxdMP5saq9m9C7NbqXH2iCHRIBAVyp5U'}, {'company_id': 2539, 'name': 'PT Ualand Events Bali', 'drive_file_id': '1TYfpkcM6tmzXw9iGKr8nCpegd6wbo2ti'}, {'company_id': 2540, 'name': 'PT Ubud Hot Stone', 'drive_file_id': '1ywwmEN8W5JRYfUB1xCgNGoyn7hwMIvbC'}, {'company_id': 2541, 'name': 'PT Ube Living Bali', 'drive_file_id': '1JFH6lSLRHQnDRUlUv1ZUVFc64lLBxY0a'}, {'company_id': 2546, 'name': 'PT Twinkle Oasis Bali', 'drive_file_id': '1fdQwfHeAnJW1mg7VZDGG4MQuiUC4zRC4'}, {'company_id': 2546, 'name': 'PT Twinkle Oasis Bali', 'drive_file_id': '1UG2er6-S_bHQLwKLmHF1eCOhnAO9Ie_Y'}, {'company_id': 2547, 'name': 'PT Twelve Hundred Bali', 'drive_file_id': '1qx296WCNAtXxj4PGG4x_hXFEEeQSPecz'}, {'company_id': 2548, 'name': 'PT Tun Artistry Studio', 'drive_file_id': '1xzTo7VxsdYdl6lhH0SraILEppbkNy7Ua'}, {'company_id': 2552, 'name': 'PT Tuckshop Partners Bali', 'drive_file_id': '1gWF5HB5U0YeQuk-iTz57IXJSNOgVd1i7'}, {'company_id': 2555, 'name': 'PT Tropix Development International', 'drive_file_id': '14FG40kghwRTjR34bSwzcfqHkIUnCYx27'}, {'company_id': 2560, 'name': 'PT Tribal Investments Indonesia', 'drive_file_id': '1VYAJ8OnlZKKPJby1t6CF90BoUaUcPF4G'}, {'company_id': 2561, 'name': 'PT Tri Hita Karana Living Space', 'drive_file_id': '1I6J4DQHDA1BQA4602FiN_0BaELBKTouE'}, {'company_id': 2564, 'name': 'PT Tripple Nickle Squad', 'drive_file_id': '10UVyPg-wHi03G_UWe9nI_cePVCXGVtJo'}, {'company_id': 2574, 'name': 'PT TRD Multitasking Merchandise', 'drive_file_id': '1qAsWsANHzfVX0DhLPTLQgbSthn6tCrjT'}, {'company_id': 2575, 'name': 'PT Travis Black Sands', 'drive_file_id': '1vvgSH1kTJdgr7NtGEecykQe9MlBr2mt7'}, {'company_id': 2575, 'name': 'PT Travis Black Sands', 'drive_file_id': '1zKoda54CMxtcnaroLlCh_hSIJUXkreke'}, {'company_id': 2576, 'name': 'PT Travel Estate Group', 'drive_file_id': '1Uca9yXy2pO82axUZjch2VJASI2TFhtO3'}, {'company_id': 2576, 'name': 'PT Travel Estate Group', 'drive_file_id': '1vnCrNFrLCy0ntBC1Ooz2OGdwZAW7Zysj'}, {'company_id': 2576, 'name': 'PT Travel Estate Group', 'drive_file_id': '1WXdbB8cLbJE_lkHKSdlJcASqIWqP8kNK'}, {'company_id': 2577, 'name': 'PT Travel Bug Team Consulting Group', 'drive_file_id': '1eMVu7MkVvqOEulVoUtLORnffQGs9rdpA'}, {'company_id': 2578, 'name': 'PT Trade Blvd Indonesia', 'drive_file_id': '177B18IIWo5XUT34nYEVRhJDxOe7vElmn'}, {'company_id': 2579, 'name': 'PT Tobe Global Solutions', 'drive_file_id': '1A_bxfBjswB1Z3izZabOemWmS05aTvQR9'}, {'company_id': 2580, 'name': 'PT Trading House Indonesia', 'drive_file_id': '1qNNwmzP5v9mfkYsq5mX-6oiFwCi8Zvo9'}, {'company_id': 2580, 'name': 'PT Trading House Indonesia', 'drive_file_id': '1r6OpWumGmkaryYiT4XLmKgIp0EPww83K'}, {'company_id': 2584, 'name': 'PT Total Woman Bali', 'drive_file_id': '18s5IzPHb9pmlNiGqFZs4tzst-pNgWj8o'}, {'company_id': 2584, 'name': 'PT Total Woman Bali', 'drive_file_id': '1CqFnbSbE6uEsJSMGRKvg9yakRARjD9oa'}, {'company_id': 2585, 'name': 'PT TLZR Investment Group', 'drive_file_id': '15pMSvvnbXwzUlua7Wk6Rc_TlVJEgr7fM'}, {'company_id': 2585, 'name': 'PT TLZR Investment Group', 'drive_file_id': '1qf0MCCeqshvoV-XWatZqiwZRqefRRLpK'}, {'company_id': 2586, 'name': 'PT TLG Future Group', 'drive_file_id': '1zLAt6dJZ-Xy4SkriRxrw2_Lpp8_EV_cg'}, {'company_id': 2588, 'name': 'PT Tirta Gaya Bali', 'drive_file_id': '1NcVwz0oxuHvDy0_lCNJfIZHgQNGuabdb'}, {'company_id': 2590, 'name': 'CV Tirta Bening', 'drive_file_id': '15SWUp804ng0vXpe-812nEo7399u8TxIS'}, {'company_id': 2590, 'name': 'CV Tirta Bening', 'drive_file_id': '1FrCrI-UuP3Nf_blkdhR-MFTZYWX3hj-3'}, {'company_id': 2590, 'name': 'CV Tirta Bening', 'drive_file_id': '1RukpiqBQrnvih8bitRIb4Wz4LAEqquEf'}, {'company_id': 2592, 'name': 'PT Three Sunshine Development', 'drive_file_id': '1a1sfxfmuaegcr2ZH57C53Oqonn4_LQEx'}, {'company_id': 2595, 'name': 'PT Three Hundred Sixty Five Software Indonesia', 'drive_file_id': '1t7hKaigo0yRK2tiZemwhtbufF3ekIZjb'}, {'company_id': 2597, 'name': 'PT The Viktoria Group', 'drive_file_id': '1gjzgsdEeSGqqgEOaYcyqxUhoJ1gI2YN-'}, {'company_id': 2597, 'name': 'PT The Viktoria Group', 'drive_file_id': '1OlUwnrPTjiDI-rwiJrtcQeriH1whqNum'}, {'company_id': 2598, 'name': 'PT Three Sixty Consulting', 'drive_file_id': '1bOAUiAWQGgSHKteOuIpt35PZFlNE2DeN'}, {'company_id': 2600, 'name': 'PT The Zeuner Bali', 'drive_file_id': '10o0dxlr_6OEKzf2BnllxMorld8qSbJna'}, {'company_id': 2600, 'name': 'PT The Zeuner Bali', 'drive_file_id': '1RrBBJCBZs7AUPHuezXD_TuVyWIcy0B3D'}, {'company_id': 2608, 'name': 'PT The Right Point', 'drive_file_id': '1kROXhs50hyNQ4wdmGtEVlrSiJIVI0pIm'}, {'company_id': 2610, 'name': 'PT The Reserve Bali', 'drive_file_id': '1yuNl5Mw3WLsybtx6d5V83WgXBfhIP1YR'}, {'company_id': 2612, 'name': 'PT The Ping Group', 'drive_file_id': '1VSkSkSMbGJL0vbFqySx51kMb9f3KTlM4'}, {'company_id': 2615, 'name': 'PT The Slow Project', 'drive_file_id': '1MqtZekcsiLO-nr93iQHgvy8kMMHhGSqB'}, {'company_id': 2617, 'name': 'PT The Other Project', 'drive_file_id': '1xCgp-vEVzZvQtdueH_kbho9lnV0cT9l1'}, {'company_id': 2618, 'name': 'PT The New Order Piece', 'drive_file_id': '1UAoD-0x9arDSpuGOacyA2OjYPpBJFqTi'}, {'company_id': 2619, 'name': 'PT The Ninth Realm', 'drive_file_id': '1rixRj6II0kydrZ3479zvmW4OLwaQyUXw'}, {'company_id': 2620, 'name': 'PT The Nazar Ali', 'drive_file_id': '11sW5JPVM2xfGgW-xAG85HhElkmpNOK1A'}, {'company_id': 2620, 'name': 'PT The Nazar Ali', 'drive_file_id': '1rQ_0ozD3xhARbgK-kNyobvA5ctPA_rAZ'}, {'company_id': 2621, 'name': 'PT The Medium Design', 'drive_file_id': '1SruPjN-5VDU02txogLF5f7CqaZSievfN'}, {'company_id': 2623, 'name': 'PT The Melting Pot', 'drive_file_id': '1Cbk-ltw_TkaexS5nVfQ-CFYYLPXfxfMD'}, {'company_id': 2624, 'name': 'PT The Nandc Group', 'drive_file_id': '1uI9DhmT-GtJSeJpJpSRXI_Ne2F4VYa2q'}, {'company_id': 2625, 'name': 'PT The Manolia Ventures', 'drive_file_id': '1Iq4FzR5oLU8mY4sby6rCnwyoJi6gU5VM'}, {'company_id': 2626, 'name': 'PT The Miracle Dose', 'drive_file_id': '16bz16Bv6aa8j_A-wKxE2YDq-NY1_-n3f'}, {'company_id': 2627, 'name': 'PT The Little Secret', 'drive_file_id': '1nEakaa6GVA9GnNi_MMXnNykGgSQ_w-qM'}, {'company_id': 2628, 'name': 'PT The Italian Guy', 'drive_file_id': '1yENbZRwNCwT8E_DQQeq224xpdapsIviP'}, {'company_id': 2629, 'name': 'PT The Lee Raincoat', 'drive_file_id': '1KIAIygz3RxyTxA56T4WyoZvX7VKILbti'}, {'company_id': 2630, 'name': 'PT The Condition Investments', 'drive_file_id': '1Ih6dLF4cpWAriDCUwiGo6eDfgbn5Ic8C'}, {'company_id': 2631, 'name': 'PT The Creative Agency', 'drive_file_id': '1Ejv4xFLjb6AzPGI91MUUAEMinC4AGTjt'}, {'company_id': 2632, 'name': 'PT The Eira Family', 'drive_file_id': '14kM9ECXd_slWSCuLprs3p70gGZjPdNlt'}, {'company_id': 2633, 'name': 'PT The County Bali', 'drive_file_id': '15TlGvb6H0elu9QS2JWt37S_mnZWUV5Wz'}, {'company_id': 2633, 'name': 'PT The County Bali', 'drive_file_id': '1uBgzx0m1oIckPD8BeXiGv8N6kxn843CY'}, {'company_id': 2633, 'name': 'PT The County Bali', 'drive_file_id': '1-xxITW5lxRzq739nfUdGcyfQ_T81AqtS'}, {'company_id': 2635, 'name': 'The Farm Hostel', 'drive_file_id': '1TjIuT2aKyFSSAlFI1qBi0A-eC7Pd58gf'}, {'company_id': 2637, 'name': 'PT The Italian Brother', 'drive_file_id': '1qmje6LRW9eZcIsrouyfin31EpNgbD-Nh'}, {'company_id': 2638, 'name': 'PT The Bara Jade', 'drive_file_id': '1zdfeDB-nqcmecRRRIdKo4Egd8GV1vCSW'}, {'company_id': 2640, 'name': 'PT The Cashew Tree Collective', 'drive_file_id': '1V_2glODonKa-4P72xekkCOA65xMvz4Qd'}, {'company_id': 2641, 'name': 'PT The Bohemian Collective', 'drive_file_id': '1JepT2RpZ_sbrFU9vvw6jPtO1Wtctgq_D'}]

class BatchProcessor:
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self.anthropic = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.drive_auth = DriveAuthManager(db_pool=None, http_client=self.http_client)

    async def get_token(self):
        # Using service account for system access
        return await self.drive_auth.get_access_token("system")

    async def download_pdf(self, file_id: str, company_name: str) -> str | None:
        token = await self.get_token()
        if not token:
            logger.error(f"Failed to get token for {company_name}")
            return None

        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        safe_name = "".join([c if c.isalnum() else "_" for c in company_name])
        dest_path = os.path.join(PDF_DIR, f"{safe_name}_{file_id}.pdf")

        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            return dest_path

        try:
            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(response.content)
            logger.info(f"Downloaded PDF for {company_name}")
            return dest_path
        except Exception as e:
            logger.error(f"Error downloading {company_name}: {e}")
            return None

    def extract_text(self, pdf_path: str) -> str:
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
        return text

    async def parse_with_llm(self, text: str, company_id: int) -> dict[str, Any]:
        prompt = f"""
Extract structured data from the following "Profil Perseroan" (Indonesian Company Profile) text.
Return ONLY a JSON object with the following schema:
{{
    "company_id": {company_id},
    "total_authorized_capital": number (IDR),
    "share_nominal_value": number (IDR per share),
    "kbli_codes": "comma-separated string",
    "shareholders": [
        {{
            "name": "string",
            "role": "direktur" | "komisaris" | "pemegang_saham",
            "shares_count": number,
            "ownership_percentage": number (0-100)
        }}
    ]
}}

Rules:
- Parse numbers (10.000.000 -> 10000000).
- If not found, use null.
- Be precise with percentages and share counts.

TEXT:
{text}
"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                return json.loads(content)
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {company_id}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return {"company_id": company_id, "error": str(e)}

    async def process_company(self, company: dict[str, Any]) -> dict[str, Any]:
        pdf_path = await self.download_pdf(company["drive_file_id"], company["name"])
        if not pdf_path:
            return {"company_id": company["company_id"], "name": company["name"], "error": "Download failed"}

        text = self.extract_text(pdf_path)
        if not text:
            return {"company_id": company["company_id"], "name": company["name"], "error": "Text extraction failed"}

        # Take first 15k chars to stay within context limits while being thorough
        data = await self.parse_with_llm(text[:15000], company["company_id"])
        data["name"] = company["name"] # Add name back for context/verification
        return data

    async def run_batch(self, companies: list[dict[str, Any]], output_file: str):
        results = []
        batch_size = 3 # Conservative batch size for rate limits
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i+batch_size]
            tasks = [self.process_company(c) for c in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            logger.info(f"Progress: {i + len(batch)}/{len(companies)}")
            await asyncio.sleep(1)

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved results to {output_file}")

    async def run(self):
        logger.info("Starting Batch 2...")
        await self.run_batch(BATCH_2, os.path.join(RESULTS_DIR, "batch_2_results.json"))

        logger.info("Starting Batch 3...")
        await self.run_batch(BATCH_3, os.path.join(RESULTS_DIR, "batch_3_results.json"))

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("Missing ANTHROPIC_API_KEY")
        sys.exit(1)
    processor = BatchProcessor()
    asyncio.run(processor.run())

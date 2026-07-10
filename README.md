# WhatsOSINT
View data of a WhatsApp number, including its status, photo, etc. 🕵🏽‍♂️

[![Join our Fanpage](https://img.shields.io/badge/Join%20Our%20Fanpage-Hack%20Underway-1.svg)](https://www.facebook.com/HackUnderway/)

<img src="https://github.com/HackUnderway/WhatsOSINT/blob/main/img/Demo.png" title="WhatsOSINT">

# 🔑 API Key
Get your API key.

Name | Key |
| ------------------- |-------------- |
| [Whatsapp Data](https://rapidapi.com/airaudoeduardo/api/whatsapp-data1) |  🔑 (Necessary) |

- Select the free plan.

When you have your API key, you can add it to the **.env** file Replacing **"Your_Api_Key"** with your actual RapidAPI key and save the changes.

<img src="https://github.com/HackUnderway/WhatsOSINT/blob/main/img/WhatsappData.png" title="WhatsOSINT">
<img src="https://github.com/HackUnderway/WhatsOSINT/blob/main/img/WhatsappData_%20API.png" title="WhatsOSINT">

> **The project is open to partners.**

# ⚙️ Checking modes (save cost)

By default WhatsOSINT does a full **live** check on every lookup. You can
switch to cheaper strategies via environment variables in your `.env`:

| `CHECK_MODE` | What it does | Cost |
| --- | --- | --- |
| `live` (default) | Always performs a fresh live WhatsApp check | Highest |
| `cache_first` | Reads the cached database first; only falls back to a live check when the number isn't cached yet | Medium |
| `cache_only` | Only reads the cached database, never does a live check | Lowest |

You can also choose the transport with `CHECK_PROVIDER`:

| `CHECK_PROVIDER` | Host | Auth |
| --- | --- | --- |
| `rapidapi` (default) | RapidAPI marketplace | `RAPIDAPI_KEY` |
| `native` | Direct `checkleaked.cc` endpoint | `NATIVE_API_KEY` (a separate, non-RapidAPI credential) |

Example `.env` for the cheapest possible checks:

```
RAPIDAPI_KEY=your_rapidapi_key
CHECK_MODE=cache_only
```

All settings are optional — omitting them reproduces the original live-check
behavior exactly. You can also set `CHECK_TIMEOUT_SECONDS` (default `60`) to
bound how long a request waits before giving up.

> ⚠️ **Never commit a real key.** The tracked `.env` ships with the
> `Your_Api_Key` placeholder — replace it locally, but do not `git commit`
> your real key back into the repo.

# SUPPORTED DISTRIBUTIONS
|Distribution | Version Check | supported | status |
----------|-------|------|-------|
|Kali Linux| 2024.3| yes| working   |
|Parrot Security OS| 6.0| yes | working   |
|Windows| 11 | yes | working   |
|BackBox| 8.1 | yes | working   |
|Arch Linux| 2024.06.01 | yes | working   |

# USAGE
```
git clone https://github.com/HackUnderway/WhatsOSINT.git
```
```
cd WhatsOSINT
```
```
python3 WhatsOSINT.py
```
# REQUIREMENTS
```
pip install -r requirements.txt
```
# DEVELOPMENT / TESTS
Install the dev tooling and run the unit tests (all HTTP is mocked — no API
key or network needed):
```
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```
# SUPPORT
Questions, bugs or suggestions to : info@hackunderway.com

# LICENSE
- [x] WhatsOSINT is licensed. 
- [x] See [LICENSE](https://github.com/HackUnderway/WhatsOSINT#MIT-1-ov-file) for more information.

We need partners and sponsors, if you're interested in support or help contact.

# SECURITY RESEARCHER

* Victor Bancayan - [@VictorBancayan](https://twitter.com/VictorBancayan) - (**CEO at [Hack Underway](https://www.instagram.com/hackunderway/)**) 

## 🔗 LINKS
[![PATREON](https://img.shields.io/badge/patreon-000000?style=for-the-badge&logo=Patreon&logoColor=white)](https://www.patreon.com/c/HackUnderway)
```
Fanpage: https://www.facebook.com/HackUnderway
X: https://twitter.com/JeyZetaOficial
Web site: https://hackunderway.com
Youtube: https://www.youtube.com/@JeyZetaOficial
```
[![Kali Linux Badge](https://img.shields.io/badge/Kali%20Linux-1793D1?logo=kalilinux&logoColor=fff&style=plastic)](https://www.facebook.com/HackUnderway/)

## ☕️ Support the project

[![Buy Me a Coffee](https://img.shields.io/badge/-Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/hackunderway)

from <img src="https://i.imgur.com/ngJCbSI.png" title="Perú"> made in <img src="https://i.imgur.com/NNfy2o6.png" title="Python"> with <img src="https://i.imgur.com/S86RzPA.png" title="Love"> by: <font color="red">Victor Bancayan</font>

© 2025

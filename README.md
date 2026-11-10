# Akuvox R20 → Telegram

Akuvox-ийн хөдөлгөөн/event болон MIME имэйлийн JPEG/PNG зургийг Telegram сувагт илгээх Python 3.12 үйлчилгээ. SMTP `2525`, HTTP `8090` портоор сонсоно. Нууц мэдээллийг зөвхөн `.env` файлд хадгална.

## Архитектур

```text
Akuvox 192.168.100.170
  ├─ SMTP → 192.168.100.245:25   ─┐
  └─ HTTP → 192.168.100.245:8090 ─┤ MikroTik dst-nat
                                 ↓
                      topnet Docker host
                      :2525 / :8090
                                 ↓ HTTPS (443)
                         Telegram суваг
```

MikroTik дээр Python, зураг боловсруулах, Telegram API дуудах ажил ажиллахгүй. Зөвхөн NAT/connection tracking хийнэ: ачаалал маш бага боловч **яг 0% гэж батлах боломжгүй**. Домофон өөрийн subnet доторх `192.168.100.245` IP руу шууд холбогдох тул Gateway/DNS-ийг өөрчлөх шаардлагагүй (хоёр төхөөрөмж ижил subnet mask-тай байх ёстой). Интернэт, DNS, Telegram HTTPS холболт topnet талд хэрэгтэй. Topnet-ийн бодит IP-г доорх тохиргоонд оруулна; RouterOS NAT-д hostname биш IP ашиглана.

## Docker суулгах

Topnet дээр Docker Engine/Desktop болон Compose plugin суусан байна. Энэ хавтсыг topnet руу байрлуулаад:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d --build
docker compose ps
docker compose logs --tail 100 -f
```

Linux дээр эхний хоёр тушаалыг `cp .env.example .env` болон өөрийн editor-оор орлуулна.

`.env` утгууд:

| Түлхүүр | Утга |
|---|---|
| TELEGRAM_TOKEN | BotFather-оос авсан bot token; заавал |
| TELEGRAM_CHAT_ID | Сувгийн `-100…` ID эсвэл `@channelusername`; заавал |
| DEVICE_NAME | Caption-д харагдах нэр |
| SMTP_USER / SMTP_PASS | Хоёуланг тохируулбал AUTH LOGIN/PLAIN шаардлагатай. SMTP_USER хоосон бол нэвтрэхгүй имэйл зөвшөөрнө |
| WEBHOOK_TOKEN | Хоосон биш бол `/event?token=...` заавал таарна |
| COOLDOWN_S | Event төрөл бүрийн завсарлага, анхдагч 15 секунд |

Bot-ыг Telegram сувгийн админ болгож, message илгээх эрх өгнө. `.env`-ийг Git-д бүү нэм. Docker build context-оос ч хассан. Тохиргоо өөрчилсний дараа `docker compose up -d --force-recreate` ажиллуулна.

## MikroTik Terminal

Topnet Docker host-ийн бодит IP нь **`119.40.100.100`**. Энэ хаяг WAN талд байгаа бөгөөд одоо байгаа WAN masquerade дүрэм буцах урсгалыг хариуцна; нэмэлт hairpin src-nat дүрэм шаардлагагүй.

```routeros
/ip firewall nat
add chain=dstnat action=dst-nat protocol=tcp src-address=192.168.100.170 dst-address=192.168.100.245 dst-port=25 to-addresses=119.40.100.100 to-ports=2525 comment="Akuvox SMTP to topnet"
add chain=dstnat action=dst-nat protocol=tcp src-address=192.168.100.170 dst-address=192.168.100.245 dst-port=8090 to-addresses=119.40.100.100 to-ports=8090 comment="Akuvox HTTP to topnet"
```

Эдгээрийг давтан ажиллуулбал давхар дүрэм үүснэ. Одоо байгаа ерөнхий NAT дүрмээс өмнө байрлуул. Firewall forward chain урсгалыг хааж байвал доорх зөвшөөрөх дүрмийг **drop дүрмээс өмнө** байрлуул:

```routeros
/ip firewall filter
add chain=forward action=accept protocol=tcp src-address=192.168.100.170 dst-address=119.40.100.100 dst-port=2525,8090 connection-nat-state=dstnat comment="Allow Akuvox to topnet"
```

### Winbox

1. **IP → Firewall → NAT → + → General**: Chain=`dstnat`, Src. Address=`192.168.100.170`, Dst. Address=`192.168.100.245`, Protocol=`tcp`, Dst. Port=`25`.
2. **Action**: Action=`dst-nat`, To Addresses=`119.40.100.100`, To Ports=`2525`. Apply/OK.
3. Дахин дүрэм нэм: ижил src/dst хаяг, Dst. Port=`8090`, Action=`dst-nat`, To Ports=`8090`, To Addresses=`119.40.100.100`.
4. **Filter Rules** дотор шаардлагатай forward allow дүрмийг дээрх Terminal-ийн талбаруудаар үүсгэж drop-оос өмнө байрлуул.

NAT дүрмийн packet counter нэмэгдэж буйг шалга. Туршилтыг өөр компьютерээс MikroTik:25 руу хийхэд source restriction-ийн улмаас ажиллахгүй; бодит домофоноос турших эсвэл topnet:2525 руу шууд тест хийнэ.

## Akuvox Web UI

`http://192.168.100.170` руу админаар орно. Firmware-аас шалтгаалж **Intercom → Motion → Email Notification** хэсэг нь **Intercom → Action → Email Notification** эсвэл **Security → Motion Detection** дотор байж болно.

| Талбар | Тохиргоо |
|---|---|
| Motion Detection | Enabled; шаардлагатай мэдрэмж/хуваарь |
| Motion Action / Notification | Email / Email Notification идэвхжүүлэх |
| SMTP Server Address | `192.168.100.245` |
| SMTP Server Port | `25` (port талбаргүй firmware ихэвчлэн 25 ашиглана) |
| SSL / TLS / STARTTLS | Disabled / None |
| SMTP Authentication | SMTP_USER тохируулсан бол Enabled |
| SMTP User / Username | `.env`-ийн SMTP_USER |
| SMTP Password | `.env`-ийн SMTP_PASS |
| Sender | `r20@akuvox.local` |
| Receiver | `alerts@akuvox.local` |
| Attach snapshot / Capture | Enabled, байгаа бол |

Sender/Receiver нь бодит mailbox байх шаардлагагүй; сервер хүлээн авагчийн домэйныг шалгахгүй. Save/Submit хийгээд **Email Test** дарна. Бодит motion үед зураг ирж буйг тусад нь шалгана.

**Phone → Action URL** (зарим firmware дээр Intercom → Action URL): Motion Detection/Motion Alarm event-ийн URL-г дараах байдлаар тохируулж идэвхжүүлнэ:

```text
http://192.168.100.245:8090/event?type=motion&token=YOUR_URL_ENCODED_WEBHOOK_TOKEN
```

Token-оо URL encode хийнэ. WEBHOOK_TOKEN хоосон бол token параметр шаардлагагүй. Firmware-д Motion action URL байхгүй бол Email Notification ашиглана. Action URL нь ихэвчлэн зураггүй GET явуулдаг; зураг авахын тулд SMTP snapshot ашигла. Ижил `motion` төрөлтэй HTTP ба SMTP нь cooldown-оо хуваалцдаг тул **зураг чухал бол зөвхөн SMTP-г идэвхжүүл**: HTTP түрүүлбэл араас ирэх имэйл cooldown-д орж болно.

## Турших

Topnet дээр:

```powershell
curl.exe http://127.0.0.1:8090/health
curl.exe "http://127.0.0.1:8090/event?type=motion&test=1&token=YOUR_URL_ENCODED_WEBHOOK_TOKEN"
curl.exe -X POST -H "Content-Type: image/jpeg" --data-binary "@snapshot.jpg" "http://127.0.0.1:8090/event?type=motion&test=1&token=YOUR_URL_ENCODED_WEBHOOK_TOKEN"
```

Linux дээр `curl.exe`-ийн оронд `curl` хэрэглэнэ. HTTP нь raw JPEG/PNG body хүлээн авна, multipart/form-data биш. Зураггүй POST/GET нь query-ийн `type`, `subject`-оос alert үүсгэнэ. Text/JSON/form body-г event талбар болгон задлахгүй. `test=1` cooldown алгасана. Health нь процессын HTTP амьд эсэхийг шалгана, Telegram хүргэлтийг шалгахгүй.

SMTP тестийг `smtp_test.py` нэрээр түр хадгалж `python smtp_test.py` ажиллуул (Python стандарт сан хангалттай):

```python
import getpass
import smtplib
from email.message import EmailMessage
from pathlib import Path

msg = EmailMessage()
msg['From'] = 'r20@akuvox.local'
msg['To'] = 'alerts@akuvox.local'
msg['Subject'] = 'Akuvox test'
msg.set_content('Домофоны SMTP холболтын тест')
photo = Path('snapshot.jpg')
if photo.exists():
    msg.add_attachment(photo.read_bytes(), maintype='image', subtype='jpeg', filename=photo.name)
with smtplib.SMTP('127.0.0.1', 2525, timeout=120) as smtp:
    user = input('SMTP_USER (хоосон бол AUTH хийхгүй): ')
    if user:
        smtp.login(user, getpass.getpass('SMTP_PASS: '))
    smtp.send_message(msg)
```

Зурагтай бол `🚨 Домофон хөдөлгөөн илэрлээ` caption, зураггүй бол `✅ Домофон Email тест амжилттай` + subject/plain text body ирнэ. Subject дотор `test` байвал cooldown алгасана. Caption timestamp нь **UTC (+00:00)**; Улаанбаатарын цагаас 8 цагийн зөрүүтэй. 2–10 зураг нэг album, түүнээс олон бол 10-аар хуваана; ганц зураг sendPhoto ашиглана. Caption 1024, text 4096 тэмдэгтээр хязгаарлана.

## Ашиглалт ба хязгаар

- SMTP/HTTP оролт 20 MiB хүртэл. Telegram photo-ийн хэмжээ/харьцааны хязгаарт нийцсэн JPEG/PNG ашигла; том/эвдэрсэн зураг хүргэлтийн алдаа өгнө.
- Cooldown нь event төрөл бүрээр санах ойд хадгалагдана, restart хийхэд арилна. SMTP нь `motion` төрөлтэй. Амжилттай хүргэлтийн дараа cooldown эхэлнэ.
- Telegram алдаа үед SMTP `451` (илгээгч retry хийх боломжтой), HTTP `502` буцаана. Дискэн queue, автоматаар дахин илгээх ажил байхгүй; Akuvox retry хийхгүй бол алдагдаж болно. Олон album-ийн зарим нь амжилттай болсон хойно retry хийвэл давхар зураг ирж болно.
- SMTP AUTH болон HTTP нь LAN дотор шифрлэгдээгүй. Тусгаарласан LAN/VPN ашиглаж, MikroTik ба topnet host firewall дээр зөвхөн шаардлагатай эх үүсвэрт нээ. Docker-ийн published портууд host-ийн бүх интерфэйс дээр нээлттэй тул интернэтэд шууд бүү гарга. WAN masquerade үед host дээр эх үүсвэр нь MikroTik-ийн WAN IP болж харагдана.
- `docker compose logs --tail 100`-оор алдааг шалга. Token, password болон query URL-г үйлчилгээ log-д бичихгүй. Telegram 502 үед bot/channel эрх, topnet DNS/HTTPS гарцыг шалга.
- Зогсоох: `docker compose down`. Шинэчлэх: `docker compose up -d --build`.

## Албан эх сурвалж

Локал хөгжүүлэлтийн шалгалт (Telegram API-г mock хийж, SMTP/HTTP холболтыг бодитоор тестэлнэ):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m unittest discover -s tests -v
```

- [aiosmtpd AUTH LOGIN/PLAIN](https://aiosmtpd.aio-libs.org/en/stable/auth.html)
- [MikroTik NAT ба hairpin](https://help.mikrotik.com/docs/spaces/ROS/pages/3211299/NAT)
- [Akuvox motion/email/action тохиргоо](https://knowledge.akuvox.com/docs/security-53)
- [Telegram Bot API](https://core.telegram.org/bots/api#sendphoto)
